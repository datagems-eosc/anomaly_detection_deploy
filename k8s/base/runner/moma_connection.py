"""
Resolve the source database connection from the dataset profile in DMM/MoMa.

DataGEMS policy: Vault only holds the database credentials (POSTGRES_USER /
POSTGRES_PASSWORD). Host, port and database name are not secrets and must be
read from the dataset profile, so they are never configured in this component.

Same flow as datagems-eosc/streaming_interval_profiler:
  1. Get a bearer token from the DataGEMS AAI (Keycloak) with the
     client-credentials grant, scope "datagems".
  2. GET {MOMA_API_URL}/api/v1/dataset/get/{dataset_id}.
  3. Read host/port/database from the dg:DatabaseConnection node's contentUrl
     (postgresql://host:port/db).

Environment variables:
  MOMA_API_URL        DMM base URL, no trailing slash (required)
  MOMA_DATASET_ID     Dataset id of the weather dataset (required)
  AAI_TOKEN_URL       Keycloak token endpoint
  AAI_CLIENT_ID       This component's AAI client id
  AAI_CLIENT_SECRET   Client secret (from Vault)
  AAI_SCOPE           Token scope, default "datagems"
  MOMA_TOKEN          Static bearer token, used only if the AAI_* vars are unset
  POSTGRES_USER       Database user (from Vault)
  POSTGRES_PASSWORD   Database password (from Vault)
"""

import os
from typing import Optional
from urllib.parse import quote, urlparse

HTTP_TIMEOUT = 15


class MomaConnectionError(RuntimeError):
    """The connection could not be resolved from DMM/MoMa."""


def moma_configured() -> bool:
    return bool(os.environ.get("MOMA_API_URL") and os.environ.get("MOMA_DATASET_ID"))


def _bearer_token() -> str:
    import requests

    token_url = os.environ.get("AAI_TOKEN_URL")
    client_id = os.environ.get("AAI_CLIENT_ID")
    client_secret = os.environ.get("AAI_CLIENT_SECRET")

    if token_url and client_id and client_secret:
        try:
            resp = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": os.environ.get("AAI_SCOPE", "datagems"),
                },
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise MomaConnectionError(f"Could not reach AAI at {token_url}: {exc}") from exc
        if not resp.ok:
            raise MomaConnectionError(
                f"AAI returned HTTP {resp.status_code} for client '{client_id}': {resp.text[:200]}"
            )
        return resp.json()["access_token"]

    token = os.environ.get("MOMA_TOKEN")
    if token:
        return token
    raise MomaConnectionError(
        "No credentials for DMM: set AAI_TOKEN_URL, AAI_CLIENT_ID and AAI_CLIENT_SECRET "
        "(or MOMA_TOKEN)."
    )


def fetch_dataset(moma_url: str, dataset_id: str, token: str) -> dict:
    """Return the dataset subgraph ({nodes, edges}) from DMM."""
    import requests

    url = f"{moma_url.rstrip('/')}/api/v1/dataset/get/{dataset_id}"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=HTTP_TIMEOUT
        )
    except requests.RequestException as exc:
        raise MomaConnectionError(f"Could not reach DMM at {url}: {exc}") from exc
    if not resp.ok:
        raise MomaConnectionError(
            f"DMM returned HTTP {resp.status_code} for dataset {dataset_id} "
            f"(GET {url}): {resp.text[:200]}"
        )

    body = resp.json()
    if isinstance(body, dict) and body.get("code") == 404:
        raise MomaConnectionError(f"Dataset {dataset_id} not found in DMM.")
    if isinstance(body, dict) and body.get("dataset"):
        return body["dataset"]
    if isinstance(body, dict) and body.get("datasets"):
        return body["datasets"][0]
    return body


def connection_from_dataset(dataset: dict) -> dict:
    """
    Extract {host, port, database} from a dataset subgraph.

    Primary source: the dg:DatabaseConnection node's contentUrl
    (postgresql://host:port/db). Fallback: a legacy properties.connection dict
    on the sc:Dataset node.
    """
    nodes = dataset.get("nodes", []) if isinstance(dataset, dict) else []
    host = port = database = None

    conn_node = next(
        (n for n in nodes if "dg:DatabaseConnection" in n.get("labels", [])), None
    )
    content_url = ((conn_node or {}).get("properties") or {}).get("contentUrl")
    if content_url:
        parsed = urlparse(content_url)
        host = parsed.hostname
        port = str(parsed.port) if parsed.port else None
        database = (parsed.path or "").lstrip("/") or None

    if not (host and database):
        dataset_node = next(
            (n for n in nodes if "sc:Dataset" in n.get("labels", [])), None
        )
        legacy = ((dataset_node or {}).get("properties") or {}).get("connection") or {}
        host = host or legacy.get("host")
        port = port or (str(legacy["port"]) if legacy.get("port") else None)
        database = database or legacy.get("database")

    if not (host and database):
        raise MomaConnectionError(
            "Dataset profile has no usable database connection: expected a "
            "dg:DatabaseConnection node with contentUrl 'postgresql://host:port/db'."
        )
    return {"host": host, "port": port or "5432", "database": database}


def resolve_connection(dataset_id: Optional[str] = None) -> dict:
    """Return {host, port, database} for the dataset, read from its MoMa profile."""
    moma_url = os.environ.get("MOMA_API_URL")
    dataset_id = dataset_id or os.environ.get("MOMA_DATASET_ID")
    if not (moma_url and dataset_id):
        raise MomaConnectionError("MOMA_API_URL and MOMA_DATASET_ID must be set.")

    dataset = fetch_dataset(moma_url, dataset_id, _bearer_token())
    conn = connection_from_dataset(dataset)
    print(
        f"Database connection resolved from MoMa dataset {dataset_id}: "
        f"{conn['host']}:{conn['port']}/{conn['database']}",
        flush=True,
    )
    return conn


def resolve_pg_url(dataset_id: Optional[str] = None) -> str:
    """Build the PostgreSQL URL: coordinates from MoMa, credentials from the environment."""
    user = os.environ.get("POSTGRES_USER")
    pwd = os.environ.get("POSTGRES_PASSWORD")
    if not (user and pwd):
        raise MomaConnectionError("POSTGRES_USER and POSTGRES_PASSWORD must be set.")

    conn = resolve_connection(dataset_id)
    return (
        f"postgresql://{quote(user, safe='')}:{quote(pwd, safe='')}"
        f"@{conn['host']}:{conn['port']}/{conn['database']}"
    )
