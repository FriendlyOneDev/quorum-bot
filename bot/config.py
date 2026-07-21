import os

# Legacy singletons — kept for anything that still reads them as "the main channel"
# (e.g. an early on_startup message). Prefer CHANNELS / MAIN_CHANNEL for new call sites.
ANNOUNCEMENTS_CHAT = os.getenv("ANNOUNCEMENTS_CHAT")
ANNOUNCEMENTS_TOPIC = int(os.getenv("ANNOUNCEMENTS_TOPIC", "0")) or None
REFRESH_INTERVAL_MINUTES = int(os.getenv("REFRESH_INTERVAL_MINUTES", "15"))


def _parse_chat(raw):
    """Numeric chat IDs (e.g. -1004387181912) get int()'d; @usernames pass through."""
    if raw is None:
        return None
    s = str(raw)
    if s.lstrip("-").isdigit():
        return int(s)
    return s


CHANNELS = [
    {
        "chat_id": _parse_chat(ANNOUNCEMENTS_CHAT),
        "topic_id": ANNOUNCEMENTS_TOPIC,
        "msg_col": "message_id",
        "photo_col": "photo_message_id",
    },
]

_academy_chat = os.getenv("ANNOUNCEMENTS_CHAT_ACADEMY")
if _academy_chat:
    CHANNELS.append({
        "chat_id": _parse_chat(_academy_chat),
        "topic_id": int(os.getenv("ANNOUNCEMENTS_TOPIC_ACADEMY", "0")) or None,
        "msg_col": "message_id_academy",
        "photo_col": "photo_message_id_academy",
    })

MAIN_CHANNEL = CHANNELS[0]
