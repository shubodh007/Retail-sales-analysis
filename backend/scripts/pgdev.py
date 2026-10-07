"""Local PostgreSQL dev-cluster helper (pgserver binaries, fixed port 5432).

Usage (from backend/ with .venv active):
    python scripts/pgdev.py start   # init (first run) + start on 127.0.0.1:5432
    python scripts/pgdev.py stop    # stop, keep data
    python scripts/pgdev.py uri     # print SQLAlchemy URIs for .env

pgserver bootstraps real PostgreSQL binaries (no admin install needed).
PostgreSQL stays the primary DB for dev AND deployment; there is no
SQLite fallback anywhere in this project.
"""
import subprocess
import sys
import time
from pathlib import Path

import pgserver
from pgserver._commands import POSTGRES_BIN_PATH, pg_ctl
from pgserver.utils import PostmasterInfo

PGDATA = Path(__file__).resolve().parents[2] / ".tools" / "pgdata"
HOST, PORT = "127.0.0.1", 5432


def _running_on_fixed_port() -> bool:
    info = PostmasterInfo.read_from_pgdata(PGDATA)
    return info is not None and info.is_running() and info.port == PORT


def start() -> None:
    if not PGDATA.exists():
        PGDATA.mkdir(parents=True)
        pgserver.get_server(str(PGDATA), cleanup_mode=None)  # bootstrap binaries + initdb
    if not _running_on_fixed_port():
        try:
            pg_ctl(["-w", "stop", "-m", "fast"], pgdata=PGDATA)
        except subprocess.CalledProcessError:
            pass  # was not running
        pg_ctl(
            ["-w", "-o", f'-h "{HOST}"', "-o", f"-p {PORT}", "-l", str(PGDATA / "log"), "start"],
            pgdata=PGDATA,
        )
        for _ in range(30):
            if _running_on_fixed_port():
                break
            time.sleep(1)
        if not _running_on_fixed_port():
            raise RuntimeError("postgres did not reach ready state on 5432")
    srv = pgserver.get_server(str(PGDATA), cleanup_mode=None)  # adopt, never restarts a live server
    print("started:", srv.get_uri("retail_intelligence"))
    import psycopg2

    conn = psycopg2.connect(host=HOST, port=PORT, user="postgres", dbname="postgres")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'retail_intelligence'")
        if cur.fetchone() is None:
            cur.execute("CREATE DATABASE retail_intelligence")
            print("created database retail_intelligence")
        else:
            print("database retail_intelligence exists")
    conn.close()


def stop() -> None:
    pg_ctl(["-w", "stop"], pgdata=PGDATA)
    print("stopped")


def uri() -> None:
    srv = pgserver.get_server(str(PGDATA), cleanup_mode=None)
    print("SYNC :", srv.get_uri("retail_intelligence").replace("postgresql://", "postgresql+psycopg2://"))
    print("ASYNC:", srv.get_uri("retail_intelligence").replace("postgresql://", "postgresql+asyncpg://"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    {"start": start, "stop": stop, "uri": uri}[cmd]()
