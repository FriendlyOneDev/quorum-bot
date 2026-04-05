import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from data_utils import (
    create_game,
    get_game,
    get_game_by_message_id,
    update_game,
    delete_game,
    get_all_games,
    get_games_by_creator,
    add_player,
    remove_player,
    add_media_file,
    get_or_create_user,
    get_user,
    get_user_by_username,
    update_user,
    get_all_users,
    set_role,
    get_role,
    is_admin,
    is_gm,
    has_gm_permission,
    get_slots,
    add_slots,
    consume_slot,
    needs_slot,
    TIMEZONE,
)


# ---------------------------------------------------------------------------
# Game CRUD
# ---------------------------------------------------------------------------

def test_create_game():
    # Need a user first (FK constraint)
    get_or_create_user(12345, "creator", "Creator")
    game = create_game(
        creator_id=12345,
        title="D&D Session",
        description="Lost Mines",
        max_players=5,
        game_date="2025-12-01 19:00",
        message_id=99999,
    )
    assert game["creator_id"] == 12345
    assert game["title"] == "D&D Session"
    assert game["description"] == "Lost Mines"
    assert game["max_players"] == 5
    assert game["players"] == []
    assert game["game_date"] == "2025-12-01 19:00"
    assert game["message_id"] == 99999
    assert game["autodelete"] is True
    assert "game_id" in game
    assert "created_at" in game


def test_create_game_autodelete_false():
    get_or_create_user(12345, "creator", "Creator")
    game = create_game(12345, "Test", "Test", 5, autodelete=False)
    assert game["autodelete"] is False


def test_get_game():
    get_or_create_user(12345, "creator", "Creator")
    created = create_game(12345, "Test", "Test", 5)
    retrieved = get_game(created["game_id"])
    assert retrieved["game_id"] == created["game_id"]
    assert retrieved["title"] == "Test"


def test_get_game_not_found():
    assert get_game("nonexistent") is None


def test_get_game_by_message_id():
    get_or_create_user(12345, "creator", "Creator")
    created = create_game(12345, "Test", "Test", 5, message_id=12345)
    retrieved = get_game_by_message_id(12345)
    assert retrieved["game_id"] == created["game_id"]


def test_get_game_by_message_id_not_found():
    assert get_game_by_message_id(99999) is None


def test_update_game():
    get_or_create_user(12345, "creator", "Creator")
    created = create_game(12345, "Original", "Desc", 5)
    success = update_game(created["game_id"], {"title": "Updated", "max_players": 6})
    assert success is True
    updated = get_game(created["game_id"])
    assert updated["title"] == "Updated"
    assert updated["max_players"] == 6
    assert updated["description"] == "Desc"


def test_update_game_not_found():
    assert update_game("nonexistent", {"title": "X"}) is False


def test_delete_game():
    get_or_create_user(12345, "creator", "Creator")
    created = create_game(12345, "Delete Me", "Test", 5)
    assert delete_game(created["game_id"]) is True
    assert get_game(created["game_id"]) is None


def test_delete_game_not_found():
    assert delete_game("nonexistent") is False


def test_get_all_games():
    get_or_create_user(12345, "c1", "C1")
    get_or_create_user(67890, "c2", "C2")
    g1 = create_game(12345, "Game 1", "D1", 5)
    g2 = create_game(67890, "Game 2", "D2", 4)
    all_games = get_all_games()
    assert len(all_games) == 2
    ids = [g["game_id"] for g in all_games]
    assert g1["game_id"] in ids
    assert g2["game_id"] in ids


def test_get_games_by_creator():
    get_or_create_user(111, "a", "A")
    get_or_create_user(222, "b", "B")
    create_game(111, "Game A", "D", 5)
    create_game(222, "Game B", "D", 5)
    create_game(111, "Game C", "D", 5)
    games = get_games_by_creator(111)
    assert len(games) == 2
    assert all(g["creator_id"] == 111 for g in games)


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

def test_add_player():
    get_or_create_user(12345, "creator", "Creator")
    get_or_create_user(99999, "player", "Player")
    game = create_game(12345, "Test", "Test", 5)
    assert add_player(game["game_id"], 99999) is True
    assert 99999 in get_game(game["game_id"])["players"]


def test_add_player_duplicate():
    get_or_create_user(12345, "creator", "Creator")
    get_or_create_user(99999, "player", "Player")
    game = create_game(12345, "Test", "Test", 5)
    add_player(game["game_id"], 99999)
    assert add_player(game["game_id"], 99999) is False
    assert get_game(game["game_id"])["players"].count(99999) == 1


def test_add_player_not_found():
    assert add_player("nonexistent", 99999) is False


def test_remove_player():
    get_or_create_user(12345, "creator", "Creator")
    get_or_create_user(99999, "player", "Player")
    game = create_game(12345, "Test", "Test", 5)
    add_player(game["game_id"], 99999)
    assert remove_player(game["game_id"], 99999) is True
    assert 99999 not in get_game(game["game_id"])["players"]


def test_remove_player_not_in_game():
    get_or_create_user(12345, "creator", "Creator")
    game = create_game(12345, "Test", "Test", 5)
    assert remove_player(game["game_id"], 99999) is False


def test_remove_player_not_found():
    assert remove_player("nonexistent", 99999) is False


def test_add_media_file():
    get_or_create_user(12345, "creator", "Creator")
    game = create_game(12345, "Test", "Test", 5)
    assert add_media_file(game["game_id"], "data/media/test.jpg") is True
    assert "data/media/test.jpg" in get_game(game["game_id"])["media_files"]


def test_add_multiple_media_files():
    get_or_create_user(12345, "creator", "Creator")
    game = create_game(12345, "Test", "Test", 5)
    add_media_file(game["game_id"], "data/media/f1.jpg")
    add_media_file(game["game_id"], "data/media/f2.png")
    files = get_game(game["game_id"])["media_files"]
    assert len(files) == 2


def test_add_media_file_not_found():
    assert add_media_file("nonexistent", "data/media/test.jpg") is False


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def test_get_or_create_user_new():
    user = get_or_create_user(111, "alice", "Alice")
    assert user["user_id"] == 111
    assert user["username"] == "alice"
    assert user["display_name"] == "Alice"
    assert user["role"] == "user"
    assert user["slots"] == 1  # welcome slot
    assert "slots_week" in user


def test_get_or_create_user_existing():
    get_or_create_user(111, "alice", "Alice")
    user = get_or_create_user(111, "alice_new", "Alice New")
    assert user["username"] == "alice_new"
    assert user["display_name"] == "Alice New"
    assert len(get_all_users()) == 1


def test_get_user():
    get_or_create_user(111, "alice", "Alice")
    user = get_user(111)
    assert user is not None
    assert user["username"] == "alice"


def test_get_user_not_found():
    assert get_user(999) is None


def test_get_user_by_username():
    get_or_create_user(111, "alice", "Alice")
    user = get_user_by_username("alice")
    assert user is not None
    assert user["user_id"] == 111


def test_get_user_by_username_with_at():
    get_or_create_user(111, "alice", "Alice")
    user = get_user_by_username("@alice")
    assert user is not None


def test_get_user_by_username_case_insensitive():
    get_or_create_user(111, "Alice", "Alice")
    user = get_user_by_username("alice")
    assert user is not None


def test_get_user_by_username_not_found():
    assert get_user_by_username("nobody") is None


def test_get_user_by_username_none():
    assert get_user_by_username(None) is None


def test_update_user():
    get_or_create_user(111, "alice", "Alice")
    assert update_user(111, {"display_name": "Alice Updated"}) is True
    assert get_user(111)["display_name"] == "Alice Updated"


def test_update_user_not_found():
    assert update_user(999, {"display_name": "X"}) is False


def test_get_all_users():
    get_or_create_user(111, "a", "A")
    get_or_create_user(222, "b", "B")
    assert len(get_all_users()) == 2


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def test_set_role():
    get_or_create_user(111, "alice", "Alice")
    assert set_role(111, "gm") is True
    assert get_user(111)["role"] == "gm"


def test_set_role_invalid():
    get_or_create_user(111, "alice", "Alice")
    assert set_role(111, "superadmin") is False


def test_get_role_default():
    get_or_create_user(111, "alice", "Alice")
    assert get_role(111) == "user"


def test_get_role_unknown_user():
    assert get_role(999) == "user"


def test_is_admin():
    get_or_create_user(111, "admin", "Admin")
    set_role(111, "admin")
    assert is_admin(111) is True
    assert is_admin(999) is False


def test_is_gm():
    get_or_create_user(111, "gm", "GM")
    set_role(111, "gm")
    assert is_gm(111) is True
    assert is_gm(999) is False


def test_has_gm_permission():
    get_or_create_user(111, "gm", "GM")
    get_or_create_user(222, "admin", "Admin")
    get_or_create_user(333, "user", "User")
    set_role(111, "gm")
    set_role(222, "admin")
    assert has_gm_permission(111) is True
    assert has_gm_permission(222) is True
    assert has_gm_permission(333) is False


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------

def test_get_slots_new_user():
    get_or_create_user(111, "alice", "Alice")
    assert get_slots(111) == 1  # welcome slot


def test_get_slots_unknown_user():
    assert get_slots(999) == 0


def test_add_slots():
    get_or_create_user(111, "alice", "Alice")
    assert add_slots(111, 3) is True
    assert get_slots(111) == 4  # 1 welcome + 3 added


def test_add_slots_unknown_user():
    assert add_slots(999, 1) is False


def test_consume_slot():
    get_or_create_user(111, "alice", "Alice")
    assert consume_slot(111) is True
    assert get_slots(111) == 0


def test_consume_slot_empty():
    get_or_create_user(111, "alice", "Alice")
    consume_slot(111)  # use the welcome slot
    assert consume_slot(111) is False


def test_slots_expire_on_new_week():
    get_or_create_user(111, "alice", "Alice")
    add_slots(111, 5)
    # Simulate week change
    update_user(111, {"slots_week": "2020-W01"})
    assert get_slots(111) == 0


def test_add_slots_on_new_week():
    get_or_create_user(111, "alice", "Alice")
    update_user(111, {"slots_week": "2020-W01"})
    add_slots(111, 2)
    assert get_slots(111) == 2


# ---------------------------------------------------------------------------
# needs_slot
# ---------------------------------------------------------------------------

def test_needs_slot_regular_user():
    get_or_create_user(111, "alice", "Alice")
    get_or_create_user(999, "creator", "Creator")
    game = create_game(999, "Game", "Desc", 5, game_date="2099-12-31 19:00")
    assert needs_slot(game, 111) is True


def test_needs_slot_gm_bypass():
    get_or_create_user(111, "gm", "GM")
    get_or_create_user(999, "creator", "Creator")
    set_role(111, "gm")
    game = create_game(999, "Game", "Desc", 5, game_date="2099-12-31 19:00")
    assert needs_slot(game, 111) is False


def test_needs_slot_admin_bypass():
    get_or_create_user(111, "admin", "Admin")
    get_or_create_user(999, "creator", "Creator")
    set_role(111, "admin")
    game = create_game(999, "Game", "Desc", 5, game_date="2099-12-31 19:00")
    assert needs_slot(game, 111) is False


def test_needs_slot_24h_exception():
    get_or_create_user(111, "alice", "Alice")
    get_or_create_user(999, "creator", "Creator")
    soon = datetime.now(TIMEZONE) + timedelta(hours=12)
    game_date = soon.strftime("%Y-%m-%d %H:%M")
    game = create_game(999, "Game", "Desc", 5, game_date=game_date)
    assert needs_slot(game, 111) is False


def test_needs_slot_no_date():
    get_or_create_user(111, "alice", "Alice")
    get_or_create_user(999, "creator", "Creator")
    game = create_game(999, "Game", "Desc", 5)
    assert needs_slot(game, 111) is True
