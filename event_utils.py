import json
import os
from datetime import datetime
from typing import Optional, List, Dict


DATA_FILE = "data/events.json"


def ensure_data_file():
    """Create data directory and events.json if they don't exist"""
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/media", exist_ok=True)

    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"events": []}, f, indent=2)


def load_events() -> List[Dict]:
    """Load all events from JSON file"""
    ensure_data_file()
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    return data.get("events", [])


def save_events(events: List[Dict]):
    """Save events list to JSON file"""
    ensure_data_file()
    with open(DATA_FILE, "w") as f:
        json.dump({"events": events}, f, indent=2)


def create_event(creator_id: int, title: str, description: str, max_players: int,
                 event_date: str = None, message_id: int = None, autodelete: bool = True) -> Dict:
    """Create a new event and save it"""
    events = load_events()

    event = {
        "event_id": f"event_{len(events) + 1}_{int(datetime.now().timestamp())}",
        "creator_id": creator_id,
        "title": title,
        "description": description,
        "max_players": max_players,
        "players": [],
        "created_at": datetime.now().isoformat(),
        "event_date": event_date,
        "media_files": [],
        "message_id": message_id,
        "autodelete": autodelete
    }

    events.append(event)
    save_events(events)
    return event


def get_event(event_id: str) -> Optional[Dict]:
    """Get a specific event by ID"""
    events = load_events()
    for event in events:
        if event["event_id"] == event_id:
            return event
    return None


def get_event_by_message_id(message_id: int) -> Optional[Dict]:
    """Get event by Telegram message ID"""
    events = load_events()
    for event in events:
        if event.get("message_id") == message_id:
            return event
    return None


def update_event(event_id: str, updates: Dict) -> bool:
    """Update an event with new data"""
    events = load_events()
    for i, event in enumerate(events):
        if event["event_id"] == event_id:
            events[i].update(updates)
            save_events(events)
            return True
    return False


def delete_event(event_id: str) -> bool:
    """Delete an event"""
    events = load_events()
    updated_events = [e for e in events if e["event_id"] != event_id]

    if len(updated_events) < len(events):
        save_events(updated_events)
        return True
    return False


def get_all_events() -> List[Dict]:
    """Get all events"""
    return load_events()


def add_player(event_id: str, player_id: int) -> bool:
    """Add a player to an event"""
    event = get_event(event_id)
    if not event:
        return False

    if player_id not in event["players"]:
        event["players"].append(player_id)
        return update_event(event_id, {"players": event["players"]})
    return False


def remove_player(event_id: str, player_id: int) -> bool:
    """Remove a player from an event"""
    event = get_event(event_id)
    if not event:
        return False

    if player_id in event["players"]:
        event["players"].remove(player_id)
        return update_event(event_id, {"players": event["players"]})
    return False


def add_media_file(event_id: str, file_path: str) -> bool:
    """Add a media file path to an event"""
    event = get_event(event_id)
    if not event:
        return False

    event["media_files"].append(file_path)
    return update_event(event_id, {"media_files": event["media_files"]})
