import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
import shutil
from event_utils import (
    ensure_data_file,
    load_events,
    save_events,
    create_event,
    get_event,
    get_event_by_message_id,
    update_event,
    delete_event,
    get_all_events,
    add_player,
    remove_player,
    add_media_file,
    DATA_FILE
)


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up test data before and after each test"""
    if os.path.exists("data"):
        shutil.rmtree("data")
    yield
    if os.path.exists("data"):
        shutil.rmtree("data")


def test_ensure_data_file():
    """Test that data directory and files are created"""
    ensure_data_file()

    assert os.path.exists("data")
    assert os.path.exists("data/media")
    assert os.path.exists(DATA_FILE)

    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    assert data == {"events": []}


def test_load_events_empty():
    """Test loading events from empty file"""
    events = load_events()
    assert events == []


def test_save_and_load_events():
    """Test saving and loading events"""
    test_events = [
        {"event_id": "test_1", "title": "Test Event"},
        {"event_id": "test_2", "title": "Another Event"}
    ]

    save_events(test_events)
    loaded_events = load_events()

    assert loaded_events == test_events


def test_create_event():
    """Test creating a new event"""
    event = create_event(
        creator_id=12345,
        title="D&D Session",
        description="Lost Mines of Phandelver",
        max_players=5,
        event_date="2025-12-01T19:00:00",
        message_id=99999
    )

    assert event["creator_id"] == 12345
    assert event["title"] == "D&D Session"
    assert event["description"] == "Lost Mines of Phandelver"
    assert event["max_players"] == 5
    assert event["players"] == []
    assert event["event_date"] == "2025-12-01T19:00:00"
    assert event["message_id"] == 99999
    assert event["autodelete"] == True
    assert "event_id" in event
    assert "created_at" in event


def test_create_event_with_autodelete_false():
    """Test creating event with autodelete=False"""
    event = create_event(
        creator_id=12345,
        title="Test",
        description="Test",
        max_players=5,
        autodelete=False
    )

    assert event["autodelete"] == False


def test_get_event():
    """Test retrieving an event by ID"""
    created_event = create_event(
        creator_id=12345,
        title="Test Event",
        description="Test",
        max_players=5
    )

    retrieved_event = get_event(created_event["event_id"])

    assert retrieved_event == created_event


def test_get_event_not_found():
    """Test retrieving non-existent event"""
    event = get_event("nonexistent_id")
    assert event is None


def test_get_event_by_message_id():
    """Test retrieving event by message ID"""
    created_event = create_event(
        creator_id=12345,
        title="Test Event",
        description="Test",
        max_players=5,
        message_id=12345
    )

    retrieved_event = get_event_by_message_id(12345)

    assert retrieved_event == created_event


def test_get_event_by_message_id_not_found():
    """Test retrieving event by non-existent message ID"""
    event = get_event_by_message_id(99999)
    assert event is None


def test_update_event():
    """Test updating an event"""
    created_event = create_event(
        creator_id=12345,
        title="Original Title",
        description="Original Description",
        max_players=5
    )

    success = update_event(created_event["event_id"], {
        "title": "Updated Title",
        "max_players": 6
    })

    assert success == True

    updated_event = get_event(created_event["event_id"])
    assert updated_event["title"] == "Updated Title"
    assert updated_event["max_players"] == 6
    assert updated_event["description"] == "Original Description"


def test_update_event_not_found():
    """Test updating non-existent event"""
    success = update_event("nonexistent_id", {"title": "Updated"})
    assert success == False


def test_delete_event():
    """Test deleting an event"""
    created_event = create_event(
        creator_id=12345,
        title="To Be Deleted",
        description="Test",
        max_players=5
    )

    success = delete_event(created_event["event_id"])
    assert success == True

    retrieved_event = get_event(created_event["event_id"])
    assert retrieved_event is None


def test_delete_event_not_found():
    """Test deleting non-existent event"""
    success = delete_event("nonexistent_id")
    assert success == False


def test_get_all_events():
    """Test getting all events"""
    event1 = create_event(12345, "Event 1", "Desc 1", 5)
    event2 = create_event(67890, "Event 2", "Desc 2", 4)
    event3 = create_event(11111, "Event 3", "Desc 3", 6)

    all_events = get_all_events()

    assert len(all_events) == 3
    assert event1 in all_events
    assert event2 in all_events
    assert event3 in all_events


def test_add_player():
    """Test adding a player to an event"""
    event = create_event(12345, "Test Event", "Test", 5)

    success = add_player(event["event_id"], 99999)
    assert success == True

    updated_event = get_event(event["event_id"])
    assert 99999 in updated_event["players"]


def test_add_player_duplicate():
    """Test adding the same player twice"""
    event = create_event(12345, "Test Event", "Test", 5)

    add_player(event["event_id"], 99999)
    success = add_player(event["event_id"], 99999)

    assert success == False

    updated_event = get_event(event["event_id"])
    assert updated_event["players"].count(99999) == 1


def test_add_player_event_not_found():
    """Test adding player to non-existent event"""
    success = add_player("nonexistent_id", 99999)
    assert success == False


def test_remove_player():
    """Test removing a player from an event"""
    event = create_event(12345, "Test Event", "Test", 5)
    add_player(event["event_id"], 99999)

    success = remove_player(event["event_id"], 99999)
    assert success == True

    updated_event = get_event(event["event_id"])
    assert 99999 not in updated_event["players"]


def test_remove_player_not_in_event():
    """Test removing a player who isn't in the event"""
    event = create_event(12345, "Test Event", "Test", 5)

    success = remove_player(event["event_id"], 99999)
    assert success == False


def test_remove_player_event_not_found():
    """Test removing player from non-existent event"""
    success = remove_player("nonexistent_id", 99999)
    assert success == False


def test_add_media_file():
    """Test adding a media file to an event"""
    event = create_event(12345, "Test Event", "Test", 5)

    success = add_media_file(event["event_id"], "data/media/test.jpg")
    assert success == True

    updated_event = get_event(event["event_id"])
    assert "data/media/test.jpg" in updated_event["media_files"]


def test_add_multiple_media_files():
    """Test adding multiple media files"""
    event = create_event(12345, "Test Event", "Test", 5)

    add_media_file(event["event_id"], "data/media/file1.jpg")
    add_media_file(event["event_id"], "data/media/file2.png")

    updated_event = get_event(event["event_id"])
    assert len(updated_event["media_files"]) == 2
    assert "data/media/file1.jpg" in updated_event["media_files"]
    assert "data/media/file2.png" in updated_event["media_files"]


def test_add_media_file_event_not_found():
    """Test adding media file to non-existent event"""
    success = add_media_file("nonexistent_id", "data/media/test.jpg")
    assert success == False
