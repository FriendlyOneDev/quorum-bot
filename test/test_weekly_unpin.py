"""weekly_posts.chat_id is TEXT, CHANNELS holds ints for numeric channels, so the
stored value and the configured one must still compare equal when deciding to
unpin last week's pin."""
import sys, os, asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import data_utils
from bot import weekly

ACADEMY = {
    "key": "academy", "name": "Academy", "chat_id": -1004387181912, "topic_id": 2,
    "msg_col": "message_id_academy", "photo_col": "photo_message_id_academy",
}


class FakeBot:
    def __init__(self):
        self.unpinned = []

    async def send_message(self, **kw):
        return type("Msg", (), {"message_id": 1354})()

    async def pin_chat_message(self, **kw):
        pass

    async def unpin_chat_message(self, chat_id, message_id):
        self.unpinned.append((chat_id, message_id))


def _patch(monkeypatch, prev_chat_id):
    monkeypatch.setattr(data_utils, "get_weekly_paused", lambda: False)
    monkeypatch.setattr(data_utils, "get_weekly_post", lambda k, w: None)
    monkeypatch.setattr(data_utils, "get_all_games", lambda: [])
    monkeypatch.setattr(data_utils, "upsert_weekly_post", lambda *a, **k: None)
    monkeypatch.setattr(
        data_utils, "get_last_weekly_post_for_channel",
        lambda key, before: {
            "channel_key": key, "iso_week": "2026-W43",
            "chat_id": prev_chat_id, "message_id": 1351,
        },
    )


def test_unpins_previous_when_stored_chat_id_is_text(monkeypatch):
    _patch(monkeypatch, "-1004387181912")  # TEXT column -> str
    bot = FakeBot()
    asyncio.run(weekly.maybe_publish_or_update_weekly(bot, ACADEMY))
    assert bot.unpinned == [(-1004387181912, 1351)]


def test_does_not_unpin_a_different_chat(monkeypatch):
    _patch(monkeypatch, "-1009999999999")
    bot = FakeBot()
    asyncio.run(weekly.maybe_publish_or_update_weekly(bot, ACADEMY))
    assert bot.unpinned == []
