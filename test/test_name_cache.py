"""The per-player get_chat_member lookups are group-rate-limited at 3s each,
so resolving the same roster twice must hit Telegram only once."""
import sys, os, asyncio, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot.handlers import common


class FakeMember:
    def __init__(self, tag):
        self.tag = tag


class CountingBot:
    def __init__(self):
        self.calls = 0

    async def get_chat_member(self, chat_id, user_id):
        self.calls += 1
        return FakeMember(f"Char{user_id}")


def setup_function():
    common._name_cache.clear()


def test_second_resolve_makes_no_api_calls():
    bot = CountingBot()
    ids = [1, 2, 3, 4, 5]
    first = asyncio.run(common.resolve_player_names(bot, -100123, ids))
    assert bot.calls == 5
    second = asyncio.run(common.resolve_player_names(bot, -100123, ids))
    assert bot.calls == 5, "cached roster must not re-hit Telegram"
    assert first == second == {i: f"Char{i}" for i in ids}


def test_cache_is_per_chat():
    bot = CountingBot()
    asyncio.run(common.resolve_player_names(bot, -100123, [7]))
    asyncio.run(common.resolve_player_names(bot, -100999, [7]))
    assert bot.calls == 2


def test_expired_entry_refetches():
    bot = CountingBot()
    asyncio.run(common.resolve_player_names(bot, -100123, [7]))
    _, name = common._name_cache[(-100123, 7)]
    common._name_cache[(-100123, 7)] = (time.monotonic() - 1, name)  # lapsed
    asyncio.run(common.resolve_player_names(bot, -100123, [7]))
    assert bot.calls == 2
