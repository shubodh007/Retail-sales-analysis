"""Single SparkSession factory. Local mode, Java 17.

Resolution order (first valid wins), so the same code runs on a Windows dev
box, a Linux container, and CI without edits:

1. ``JAVA_HOME`` env var, when it points at a real JDK (>= 17 for Spark 3.5).
2. The portable ``.tools/jdk17/...`` tree (local Windows development).
3. Whatever ``java`` is on PATH (production container installs Java 17).

Same for the PostgreSQL JDBC jar: ``POSTGRES_JDBC_JAR`` env, then the
``.tools/jdbc`` copy, then ``/opt/jdbc/postgresql.jar`` (Docker image).

Workers bind loopback only (SPARK_LOCAL_IP). No Java is ever downloaded at
runtime — the container image ships it (see Dockerfile).
"""
import os
import sys
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
TOOLS_JDK = REPO_ROOT / ".tools" / "jdk17" / "jdk-17.0.20.1+1"
TOOLS_HADOOP = REPO_ROOT / ".tools" / "hadoop"
TOOLS_JDBC = REPO_ROOT / ".tools" / "jdbc" / "postgresql-42.7.4.jar"
DOCKER_JDBC = Path("/opt/jdbc/postgresql.jar")


def resolve_java_home() -> str | None:
    env = os.environ.get("JAVA_HOME")
    if env and Path(env).is_dir():
        return env
    if TOOLS_JDK.is_dir():
        return str(TOOLS_JDK)
    return None  # fall back to `java` on PATH (container provides Java 17)


def resolve_jdbc_jar() -> str | None:
    env = os.environ.get("POSTGRES_JDBC_JAR")
    if env and Path(env).is_file():
        return env
    if TOOLS_JDBC.is_file():
        return str(TOOLS_JDBC)
    if DOCKER_JDBC.is_file():
        return str(DOCKER_JDBC)
    return None


def _configure_env() -> None:
    java_home = resolve_java_home()
    if java_home:
        os.environ["JAVA_HOME"] = java_home
    if TOOLS_HADOOP.is_dir():  # Windows-only helper (winutils); absent on Linux
        os.environ.setdefault("HADOOP_HOME", str(TOOLS_HADOOP))
        os.environ["PATH"] = str(TOOLS_HADOOP / "bin") + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)


@lru_cache(maxsize=1)
def get_spark(app_name: str = "retail-intelligence"):
    from app.core.config import get_settings

    _configure_env()
    jdbc_jar = resolve_jdbc_jar()
    if jdbc_jar is None:
        raise RuntimeError(
            "PostgreSQL JDBC jar not found. Set POSTGRES_JDBC_JAR or see "
            "docs/java-spark-setup.md / Dockerfile."
        )
    from pyspark.sql import SparkSession

    settings = get_settings()
    spark = (
        SparkSession.builder.master(settings.spark_master)
        .appName(app_name)
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.memory", settings.spark_driver_memory)
        .config("spark.sql.shuffle.partitions", str(settings.spark_partitions))
        .config("spark.sql.session.timeZone", "GMT")
        # JVM zone pinned to GMT: instant-identical to UTC and accepted by
        # every PostgreSQL build (the local pgserver binaries ship without
        # tzdata and reject TimeZone=UTC on JDBC connections).
        # All dataset dates are UTC-normalized.
        .config("spark.driver.extraJavaOptions", "-Duser.timezone=GMT")
        .config("spark.jars", jdbc_jar)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark
