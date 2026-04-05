import os
import pytest

# Override DATABASE_URL before any imports of db/data_utils
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://friendlyone:bigbigdbsmallsmall@192.168.3.16:5432/quorum_test",
)

import db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Run migrations once per test session."""
    db.init_db()
    yield
    db.close_pool()


@pytest.fixture(autouse=True)
def clean_tables():
    """Truncate all tables between tests."""
    yield
    with db.get_conn() as conn:
        cur = conn.cursor()
        cur.execute("TRUNCATE game_media, game_players, games, users CASCADE")
        cur.execute("ALTER SEQUENCE game_id_seq RESTART WITH 1")
