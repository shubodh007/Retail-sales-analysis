# Java + Spark setup (Windows, no admin)

System Java (e.g. Java 25) is left untouched. Spark uses a portable
Eclipse Temurin 17 tree under `.tools/` (gitignored, re-provisioned per machine).

## Provision

```powershell
# 1. JDK 17 (~190 MB)
curl.exe -L -o .tools\jdk17.zip "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse"
Expand-Archive -Path .tools\jdk17.zip -DestinationPath .tools\jdk17 -Force
Remove-Item .tools\jdk17.zip

# 2. winutils (Hadoop 3.3.x file IO on Windows, ~200 KB)
New-Item -ItemType Directory -Path ".tools\hadoop\bin" -Force
curl.exe -L -o .tools\hadoop\bin\winutils.exe "https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.5/bin/winutils.exe"
curl.exe -L -o .tools\hadoop\bin\hadoop.dll "https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.5/bin/hadoop.dll"
```

Expected tree: `.tools/jdk17/jdk-17.0.20.1+1/`, `.tools/hadoop/bin/{winutils.exe,hadoop.dll}`.

## Verify (Phase 1 gate)

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
$env:JAVA_HOME="D:\bdapbl\.tools\jdk17\jdk-17.0.20.1+1"  # or set machine-wide
..\.tools\jdk17\jdk-17.0.20.1+1\bin\java.exe -version     # must say 17
python -m pytest tests/ -q                                # exercises Spark end to end
```

`app/spark/session.py` sets JAVA_HOME/HADOOP_HOME/SPARK_LOCAL_IP itself, so the
API works without manual env as long as `.tools/` exists.

## Verified matrix (2026-09-30, Spark 3.5.4 + Temurin 17.0.20.1 + Python 3.12)

| Path | Result |
|---|---|
| SparkSession create, `spark.range().count()` | OK |
| CSV read, count, groupBy/agg/show, describe, filter | OK |
| Parquet write + read-back (needs HADOOP_HOME/winutils) | OK |
| `parallelize(...).collect()` (ints, tuples, strings, dicts, repeated) | OK |
| `parallelize(...).count()` (Python rows + JVM shuffle agg) | FAILS |
| `createDataFrame` from driver-local rows (any action) | FAILS |

Failure mode: `Python worker exited unexpectedly (crashed)`, `EOFException`
reading from the worker; the worker process itself exits 0 with no stderr.
JVM-only and file-backed paths are unaffected.

## Consequence (by design, not by accident)

The pipeline never puts driver-local data into Spark: uploads are staged to
disk and read with `spark.read.csv`; curation writes Parquet; Postgres holds
metadata. `createDataFrame`-from-rows and Python UDFs are banned from
`app/` until the worker issue is root-caused (suspect: bundled cloudpickle vs
Python 3.12 in the SQL converter path). Revisit in a later phase; do not
"fix" by adding dependencies blindly.
