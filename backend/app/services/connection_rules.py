"""Rules for creating and editing database connections."""
from typing import Any, Dict

from sqlalchemy.engine import make_url

# Fields baked into the pooled engine when it is created. Changing one means
# the engine must be rebuilt; a rename touches none of them.
POOL_FIELDS = {"host", "port", "database", "username", "password", "is_read_only", "is_active"}

_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def needs_pool_refresh(changes: Dict[str, Any]) -> bool:
    return bool(POOL_FIELDS & changes.keys())


def _same_host(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or (a in _LOOPBACK and b in _LOOPBACK)


def is_metadata_database(host: str, port: int, database: str, metadata_url: str) -> bool:
    """Whether a connection would point at the app's own metadata database.

    That database holds every connection's credentials, so it must never
    become something a question can be asked about.
    """
    meta = make_url(metadata_url)
    return (
        database == meta.database
        and int(port) == int(meta.port or 5432)
        and _same_host(host, meta.host or "localhost")
    )
