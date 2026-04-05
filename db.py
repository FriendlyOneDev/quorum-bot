import os
import glob
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

_pool = None

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def _get_pool():
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = pool.SimpleConnectionPool(minconn=1, maxconn=5, dsn=database_url)
    return _pool


@contextmanager
def get_conn():
    p = _get_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


def init_db():
    """Run pending SQL migrations."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cur.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}

        migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
        for filepath in migration_files:
            version = os.path.basename(filepath)
            if version not in applied:
                with open(filepath, "r") as f:
                    sql = f.read()
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )


def close_pool():
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def reset_pool():
    """Close and discard the current pool so the next get_conn() creates a fresh one."""
    close_pool()
