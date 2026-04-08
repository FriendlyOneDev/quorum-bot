import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict

from db import get_conn

TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Europe/Kyiv"))

# Column lists for consistent dict assembly
_GAME_COLS = (
    "game_id", "creator_id", "title", "description", "max_players",
    "created_at", "game_date", "location", "tone", "message_id", "photo_id", "autodelete",
)
_USER_COLS = ("user_id", "username", "display_name", "role", "slots", "slots_week")


def _row_to_game(row, conn) -> Dict:
    """Convert a games table row + related data into the dict format handlers expect."""
    game = dict(zip(_GAME_COLS, row))
    game["created_at"] = game["created_at"].isoformat() if game["created_at"] else None

    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM game_players WHERE game_id = %s ORDER BY joined_at",
        (game["game_id"],),
    )
    game["players"] = [r[0] for r in cur.fetchall()]

    cur.execute(
        "SELECT file_path FROM game_media WHERE game_id = %s ORDER BY id",
        (game["game_id"],),
    )
    game["media_files"] = [r[0] for r in cur.fetchall()]

    return game


def _row_to_user(row) -> Dict:
    return dict(zip(_USER_COLS, row))


# ---------------------------------------------------------------------------
# Game CRUD
# ---------------------------------------------------------------------------

def create_game(creator_id: int, title: str, description: str, max_players: int,
                game_date: str = None, location: str = None, tone: str = None,
                message_id: int = None, autodelete: bool = True) -> Dict:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT nextval('game_id_seq')")
        seq = cur.fetchone()[0]
        game_id = f"game_{seq}_{int(datetime.now().timestamp())}"
        created_at = datetime.now().isoformat()

        cur.execute(
            """INSERT INTO games (game_id, creator_id, title, description, max_players,
                                  created_at, game_date, location, tone, message_id, photo_id, autodelete)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s)""",
            (game_id, creator_id, title, description, max_players,
             created_at, game_date, location, tone, message_id, autodelete),
        )

    return {
        "game_id": game_id,
        "creator_id": creator_id,
        "title": title,
        "description": description,
        "max_players": max_players,
        "players": [],
        "created_at": created_at,
        "game_date": game_date,
        "location": location,
        "tone": tone,
        "media_files": [],
        "message_id": message_id,
        "photo_id": None,
        "autodelete": autodelete,
    }


def get_game(game_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(_GAME_COLS)} FROM games WHERE game_id = %s",
            (game_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_game(row, conn)


def get_game_by_message_id(message_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(_GAME_COLS)} FROM games WHERE message_id = %s",
            (message_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_game(row, conn)


def update_game(game_id: str, updates: Dict) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()

        # Check game exists
        cur.execute("SELECT 1 FROM games WHERE game_id = %s", (game_id,))
        if not cur.fetchone():
            return False

        # Handle players list sync
        if "players" in updates:
            player_ids = updates.pop("players")
            cur.execute("DELETE FROM game_players WHERE game_id = %s", (game_id,))
            for pid in player_ids:
                cur.execute(
                    "INSERT INTO game_players (game_id, user_id) VALUES (%s, %s)",
                    (game_id, pid),
                )

        # Handle media_files list sync
        if "media_files" in updates:
            file_paths = updates.pop("media_files")
            cur.execute("DELETE FROM game_media WHERE game_id = %s", (game_id,))
            for fp in file_paths:
                cur.execute(
                    "INSERT INTO game_media (game_id, file_path) VALUES (%s, %s)",
                    (game_id, fp),
                )

        # Update scalar fields
        if updates:
            set_parts = []
            values = []
            for key, val in updates.items():
                set_parts.append(f"{key} = %s")
                values.append(val)
            values.append(game_id)
            cur.execute(
                f"UPDATE games SET {', '.join(set_parts)} WHERE game_id = %s",
                values,
            )

        return True


def delete_game(game_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM games WHERE game_id = %s", (game_id,))
        return cur.rowcount > 0


def get_all_games() -> List[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {', '.join(_GAME_COLS)} FROM games ORDER BY created_at")
        rows = cur.fetchall()
        return [_row_to_game(row, conn) for row in rows]


def get_games_by_creator(creator_id: int) -> List[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(_GAME_COLS)} FROM games WHERE creator_id = %s ORDER BY created_at",
            (creator_id,),
        )
        rows = cur.fetchall()
        return [_row_to_game(row, conn) for row in rows]


def add_player(game_id: str, player_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM games WHERE game_id = %s", (game_id,))
        if not cur.fetchone():
            return False
        try:
            cur.execute(
                "INSERT INTO game_players (game_id, user_id) VALUES (%s, %s)",
                (game_id, player_id),
            )
            return True
        except Exception:
            conn.rollback()
            return False


def remove_player(game_id: str, player_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM games WHERE game_id = %s", (game_id,))
        if not cur.fetchone():
            return False
        cur.execute(
            "DELETE FROM game_players WHERE game_id = %s AND user_id = %s",
            (game_id, player_id),
        )
        return cur.rowcount > 0


def add_media_file(game_id: str, file_path: str) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM games WHERE game_id = %s", (game_id,))
        if not cur.fetchone():
            return False
        cur.execute(
            "INSERT INTO game_media (game_id, file_path) VALUES (%s, %s)",
            (game_id, file_path),
        )
        return True


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def _current_week() -> str:
    return datetime.now(TIMEZONE).strftime("%G-W%V")


def get_or_create_user(user_id: int, username: str = None, display_name: str = None) -> Dict:
    with get_conn() as conn:
        cur = conn.cursor()
        slots_week = _current_week()

        # Try insert, on conflict update username/display_name if provided
        if username or display_name:
            set_parts = []
            if username:
                set_parts.append("username = EXCLUDED.username")
            if display_name:
                set_parts.append("display_name = EXCLUDED.display_name")
            set_clause = ", ".join(set_parts)
            cur.execute(
                f"""INSERT INTO users (user_id, username, display_name, role, slots, slots_week)
                    VALUES (%s, %s, %s, 'user', 1, %s)
                    ON CONFLICT (user_id) DO UPDATE SET {set_clause}
                    RETURNING {', '.join(_USER_COLS)}""",
                (user_id, username, display_name, slots_week),
            )
        else:
            cur.execute(
                f"""INSERT INTO users (user_id, username, display_name, role, slots, slots_week)
                    VALUES (%s, %s, %s, 'user', 1, %s)
                    ON CONFLICT (user_id) DO NOTHING
                    RETURNING {', '.join(_USER_COLS)}""",
                (user_id, username, display_name, slots_week),
            )

        row = cur.fetchone()
        if row:
            return _row_to_user(row)

        # Row already existed and DO NOTHING was hit — fetch it
        cur.execute(
            f"SELECT {', '.join(_USER_COLS)} FROM users WHERE user_id = %s",
            (user_id,),
        )
        return _row_to_user(cur.fetchone())


def get_user(user_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(_USER_COLS)} FROM users WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        return _row_to_user(row) if row else None


def get_user_by_username(username: str) -> Optional[Dict]:
    if not username:
        return None
    clean = username.lstrip("@").lower()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(_USER_COLS)} FROM users WHERE LOWER(username) = %s",
            (clean,),
        )
        row = cur.fetchone()
        return _row_to_user(row) if row else None


def update_user(user_id: int, updates: Dict) -> bool:
    if not updates:
        return False
    with get_conn() as conn:
        cur = conn.cursor()
        set_parts = []
        values = []
        for key, val in updates.items():
            set_parts.append(f"{key} = %s")
            values.append(val)
        values.append(user_id)
        cur.execute(
            f"UPDATE users SET {', '.join(set_parts)} WHERE user_id = %s",
            values,
        )
        return cur.rowcount > 0


def get_all_users() -> List[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {', '.join(_USER_COLS)} FROM users ORDER BY user_id")
        return [_row_to_user(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def set_role(user_id: int, role: str) -> bool:
    if role not in ("admin", "gm", "user"):
        return False
    return update_user(user_id, {"role": role})


def get_role(user_id: int) -> str:
    user = get_user(user_id)
    return user["role"] if user else "user"


def is_admin(user_id: int) -> bool:
    return get_role(user_id) == "admin"


def is_gm(user_id: int) -> bool:
    return get_role(user_id) == "gm"


def has_gm_permission(user_id: int) -> bool:
    return get_role(user_id) in ("gm", "admin")


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------

def get_slots(user_id: int) -> int:
    user = get_user(user_id)
    if not user:
        return 0
    current_week = _current_week()
    if user.get("slots_week") != current_week:
        update_user(user_id, {"slots": 0, "slots_week": current_week})
        return 0
    return user.get("slots", 0)


def add_slots(user_id: int, count: int = 1) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    current_week = _current_week()
    if user.get("slots_week") != current_week:
        new_slots = max(0, count)
        update_user(user_id, {"slots": new_slots, "slots_week": current_week})
    else:
        new_slots = max(0, user.get("slots", 0) + count)
        update_user(user_id, {"slots": new_slots})
    return True


def consume_slot(user_id: int) -> bool:
    current = get_slots(user_id)
    if current <= 0:
        return False
    return update_user(user_id, {"slots": current - 1})


def needs_slot(game: Dict, user_id: int) -> bool:
    if has_gm_permission(user_id):
        return False

    game_date_str = game.get("game_date")
    if game_date_str:
        try:
            game_dt = datetime.strptime(game_date_str, "%Y-%m-%d %H:%M")
            game_dt = game_dt.replace(tzinfo=TIMEZONE)
            now = datetime.now(TIMEZONE)
            if (game_dt - now).total_seconds() < 24 * 3600:
                return False
        except ValueError:
            pass

    return True


# ---------------------------------------------------------------------------
# Migration from JSON (one-time)
# ---------------------------------------------------------------------------

def migrate_from_events():
    """One-time migration from data/events.json into PostgreSQL. Idempotent."""
    old_file = "data/events.json"
    if not os.path.exists(old_file):
        return

    # Skip if games already exist in DB
    if get_all_games():
        return

    with open(old_file, "r") as f:
        data = json.load(f)

    old_events = data.get("events", [])
    if not old_events:
        return

    # Collect unique creator IDs — ensure they exist as users
    creator_ids = {e["creator_id"] for e in old_events}
    for cid in creator_ids:
        get_or_create_user(cid)

    # Collect unique player IDs
    for event in old_events:
        for pid in event.get("players", []):
            get_or_create_user(pid)

    # Insert games
    for event in old_events:
        game_id = event.get("event_id", "").replace("event_", "game_")
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO games (game_id, creator_id, title, description, max_players,
                                      created_at, game_date, message_id, photo_id, autodelete)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (game_id, event["creator_id"], event["title"], event["description"],
                 event["max_players"], event.get("created_at", datetime.now().isoformat()),
                 event.get("event_date"), event.get("message_id"),
                 event.get("photo_id"), event.get("autodelete", True)),
            )
            for pid in event.get("players", []):
                cur.execute(
                    "INSERT INTO game_players (game_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (game_id, pid),
                )
            for fp in event.get("media_files", []):
                cur.execute(
                    "INSERT INTO game_media (game_id, file_path) VALUES (%s, %s)",
                    (game_id, fp),
                )
