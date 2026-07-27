"""Thread-safe DB pool for the Flask web process.

The bot uses a SimpleConnectionPool (single-threaded polling loop). Gunicorn
serves requests from multiple worker threads, so the web process needs its own
ThreadedConnectionPool. Importing this module swaps `db.get_conn` in place so
every `data_utils.get_*` helper transparently uses the threaded pool.
"""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

import db

load_dotenv()

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=dsn)
    return _pool


@contextmanager
def get_conn():
    p = _get_pool()
    conn = p.getconn()
    try:
        if conn.closed:
            p.putconn(conn, close=True)
            conn = p.getconn()
        else:
            try:
                conn.cursor().execute("SELECT 1")
                conn.rollback()
            except Exception:
                p.putconn(conn, close=True)
                conn = p.getconn()
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        p.putconn(conn)


# `data_utils` does `from db import get_conn`, which binds the name at import
# time. Patch both to survive whichever module was imported first.
db.get_conn = get_conn
try:
    import data_utils
    data_utils.get_conn = get_conn
except Exception:
    # If data_utils isn't importable yet, the `from db import get_conn`
    # inside it will pick up the patched name.
    pass
