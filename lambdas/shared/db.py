import os
from psycopg_pool import ConnectionPool

_POOL: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _POOL
    if _POOL is None:
        conninfo = os.environ["DATABASE_URL"]
        _POOL = ConnectionPool(conninfo, min_size=1, max_size=2, timeout=10)
    return _POOL
