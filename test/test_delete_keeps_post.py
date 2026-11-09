"""/delete leaves the channel announcement in place and only strips its buttons."""
import sys, os, asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot.handlers import post

CHANNELS = [
    {"key": "main", "chat_id": "@Main", "topic_id": None,
     "msg_col": "message_id", "photo_col": "photo_message_id"},
    {"key": "academy", "chat_id": -1004387181912, "topic_id": 2,
     "msg_col": "message_id_academy", "photo_col": "photo_message_id_academy"},
]

GAME = {
    "game_id": "game_1_1", "message_id": 80, "photo_message_id": 79,
    "message_id_academy": 1351, "photo_message_id_academy": 1350,
}


class FakeBot:
    def __init__(self, fail_on=None):
        self.stripped, self.deleted, self.fail_on = [], [], fail_on

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup):
        if chat_id == self.fail_on:
            raise RuntimeError("Message to edit not found")
        assert reply_markup is None
        self.stripped.append((chat_id, message_id))

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))


def test_strips_buttons_in_every_channel_and_deletes_nothing(monkeypatch):
    monkeypatch.setattr(post, "CHANNELS", CHANNELS)
    bot = FakeBot()
    asyncio.run(post.strip_posted_keyboard(bot, GAME))
    assert bot.stripped == [("@Main", 80), (-1004387181912, 1351)]
    assert bot.deleted == [], "the announcement must survive /delete"


def test_one_channel_failing_does_not_stop_the_other(monkeypatch):
    monkeypatch.setattr(post, "CHANNELS", CHANNELS)
    bot = FakeBot(fail_on="@Main")
    asyncio.run(post.strip_posted_keyboard(bot, GAME))
    assert bot.stripped == [(-1004387181912, 1351)]


def test_unposted_channel_is_skipped(monkeypatch):
    monkeypatch.setattr(post, "CHANNELS", CHANNELS)
    bot = FakeBot()
    asyncio.run(post.strip_posted_keyboard(bot, {"game_id": "g", "message_id": 80}))
    assert bot.stripped == [("@Main", 80)]
