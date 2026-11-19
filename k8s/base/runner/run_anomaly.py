import importlib
import os
import sys
import time

password = os.environ.get("POSTGRES_PASSWORD", "")

def redact(value):
    text = str(value)
    if password:
        text = text.replace(password, "***")
    return text

def safe_print(*args, **kwargs):
    print(*(redact(arg) for arg in args), **kwargs)

try:
    import psycopg2

    original_connect = psycopg2.connect

    def connect_with_retry(*args, **kwargs):
        kwargs.setdefault("connect_timeout", int(os.environ.get("PGCONNECT_TIMEOUT", "10")))
        attempts = int(os.environ.get("PGCONNECT_RETRIES", "6"))
        delay = float(os.environ.get("PGCONNECT_RETRY_DELAY", "5"))

        for attempt in range(1, attempts + 1):
            try:
                return original_connect(*args, **kwargs)
            except psycopg2.OperationalError as exc:
                safe_print(
                    f"PostgreSQL connect attempt {attempt}/{attempts} failed: {redact(exc)}",
                    flush=True,
                )
                if attempt == attempts:
                    raise
                time.sleep(delay)

    psycopg2.connect = connect_with_retry
except ImportError:
    pass

# Database coordinates come from the MoMa dataset profile, not from Vault.
# Resolve them here and expose them through the variables the scripts already
# read, so the lookup works with any image tag.
import moma_connection

if moma_connection.moma_configured():
    try:
        conn = moma_connection.resolve_connection()
    except moma_connection.MomaConnectionError as exc:
        raise SystemExit(f"Could not resolve the database connection from MoMa: {redact(exc)}")
    os.environ["POSTGRES_TIMESCALE_HOST"] = conn["host"]
    os.environ["POSTGRES_TIMESCALE_PORT"] = conn["port"]
    os.environ["POSTGRES_DB"] = conn["database"]

# Without a database host the scripts silently fall back to a local SQLite file
# that does not exist in the cluster; fail instead of reporting an empty run.
if os.environ.get("REQUIRE_POSTGRES", "").lower() in ("1", "true", "yes"):
    missing = [v for v in ("POSTGRES_TIMESCALE_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD")
               if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"REQUIRE_POSTGRES is set but {', '.join(missing)} is missing.")

if len(sys.argv) < 2:
    raise SystemExit("usage: run_anomaly.py <script> [args...]")

target = sys.argv[1]
sys.argv = sys.argv[1:]
sys.path.insert(0, os.getcwd())
module_name = os.path.splitext(os.path.basename(target))[0]
module = importlib.import_module(module_name)
module.print = safe_print
module.main()
