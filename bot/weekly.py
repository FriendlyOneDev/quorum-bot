"""Per-channel weekly pinned schedule.

One message per (channel, ISO week). Publishes on the first refresh tick of
the ISO week (Monday 00:00 Europe/Kyiv, aligned with the slot rollover),
re-edited each tick as games change. Prior-week message is best-effort
unpinned when a new week's message goes up.

Wired into `_refresh_all_posts` in bot/main.py — no separate scheduler.
"""
import hashlib
import html
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List

import data_utils
from bot.config import CHANNELS
from bot.handlers.common import _get_gm_display_name

logger = logging.getLogger(__name__)

DESCRIPTION_EXCERPT_LIMIT = 100

_DAY_NAMES_UK = {
    0: "Понеділок", 1: "Вівторок", 2: "Середа", 3: "Четвер",
    4: "П'ятниця", 5: "Субота", 6: "Неділя",
}

_MONTH_NAMES_UK = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня", 5: "травня", 6: "червня",
    7: "липня", 8: "серпня", 9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня",
}


def iso_week_now() -> str:
    """Current ISO week in Kyiv time, formatted like '2026-W32' (matches slots_week)."""
    return datetime.now(data_utils.TIMEZONE).strftime("%G-W%V")


def week_bounds(iso_week: str):
    """Return (monday_naive, sunday_naive) for the given ISO week key.
    Naive datetimes so we can compare cleanly against `game_date` (also naive)."""
    year_str, week_str = iso_week.split("-W")
    monday = datetime.strptime(f"{year_str}-{week_str}-1", "%G-%V-%u")
    sunday = monday + timedelta(days=6, hours=23, minutes=59)
    return monday, sunday


def _strip_html(s: str) -> str:
    """Rough HTML-to-plaintext for the description excerpt."""
    s = re.sub(r"<[^>]+>", "", s or "")
    s = html.unescape(s)
    return " ".join(s.split())


def _excerpt(description: str, limit: int = DESCRIPTION_EXCERPT_LIMIT) -> str:
    plain = _strip_html(description)
    if len(plain) <= limit:
        # quote=False keeps apostrophes/quotes intact — only <, >, & need escaping in text content.
        return html.escape(plain, quote=False)
    cut = plain[:limit].rsplit(" ", 1)[0].rstrip(",.;:!?—-")
    return html.escape(cut, quote=False) + "…"


def _link_for_channel(channel: Dict, message_id: int, label: str) -> str:
    """Build the t.me link to a message in THIS channel, not the main one."""
    if not (message_id and channel.get("chat_id")):
        return html.escape(label, quote=False)
    chat_str = str(channel["chat_id"])
    if chat_str.startswith("@"):
        base = f"https://t.me/{chat_str[1:]}"
    else:
        link_id = chat_str.lstrip("-")
        if link_id.startswith("100"):
            link_id = link_id[3:]
        base = f"https://t.me/c/{link_id}"
    topic_id = channel.get("topic_id")
    if topic_id:
        url = f"{base}/{topic_id}/{message_id}"
    else:
        url = f"{base}/{message_id}"
    return f'<a href="{url}">{html.escape(label, quote=False)}</a>'


def _games_for_channel_week(channel: Dict, iso_week: str) -> List[Dict]:
    """All games in this channel with a game_date inside the week.
    Excludes cancelled games and games with a NULL msg_col in this channel."""
    monday, sunday = week_bounds(iso_week)
    msg_col = channel["msg_col"]
    out = []
    for g in data_utils.get_all_games():
        if g.get("cancelled"):
            continue
        if not g.get(msg_col):
            continue
        gd = g.get("game_date")
        if not gd:
            continue
        try:
            dt = datetime.strptime(gd, "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if monday <= dt <= sunday:
            g["_dt"] = dt
            out.append(g)
    out.sort(key=lambda g: g["_dt"])
    return out


def render_weekly(channel: Dict, iso_week: str) -> str:
    """Full HTML body of the weekly message for one channel."""
    monday, sunday = week_bounds(iso_week)
    header = (
        f"🗓 <b>Розклад ігор — {channel['name']}</b>\n"
        f"{monday.day} {_MONTH_NAMES_UK[monday.month]} — "
        f"{sunday.day} {_MONTH_NAMES_UK[sunday.month]}"
    )

    games = _games_for_channel_week(channel, iso_week)
    if not games:
        return header + "\n\nНаразі ігор цього тижня немає."

    lines = [header]
    last_day = None
    for g in games:
        dt = g["_dt"]
        if dt.date() != last_day:
            lines.append("")
            lines.append(f"🗓 <b>{_DAY_NAMES_UK[dt.weekday()]} {dt.strftime('%d.%m')}</b>")
            last_day = dt.date()

        title_link = _link_for_channel(channel, g.get(channel["msg_col"]), g["title"])
        gm_name = _get_gm_display_name(g.get("creator_id")) or "?"
        fill = f"{len(g.get('players', []))}/{g['max_players']}"
        location = g.get("location") or ""
        loc_part = f" · {html.escape(location, quote=False)}" if location else ""

        lines.append(f"🎲 {dt.strftime('%H:%M')} {title_link} — {html.escape(gm_name, quote=False)}")
        lines.append(f"    {fill}{loc_part}")
        excerpt = _excerpt(g.get("description", ""))
        if excerpt:
            lines.append(f"    {excerpt}")

    return "\n".join(lines)


def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def maybe_publish_or_update_weekly(bot, channel: Dict) -> None:
    """One channel, one tick: publish the current-week pin if missing, else edit
    only if the rendered content actually changed. No-op when the global
    weekly-pause flag is set."""
    if data_utils.get_weekly_paused():
        return
    if not channel.get("chat_id"):
        return

    iso_week = iso_week_now()
    text = render_weekly(channel, iso_week)
    content_hash = _hash_content(text)
    existing = data_utils.get_weekly_post(channel["key"], iso_week)

    if existing is None:
        # First publish for this (channel, week).
        try:
            sent = await bot.send_message(
                chat_id=channel["chat_id"],
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                disable_notification=True,
                message_thread_id=channel.get("topic_id"),
            )
        except Exception as e:
            logger.warning(
                "WEEKLY publish failed channel=%s week=%s: %s",
                channel["key"], iso_week, e,
            )
            return

        try:
            await bot.pin_chat_message(
                chat_id=channel["chat_id"],
                message_id=sent.message_id,
                disable_notification=True,
            )
        except Exception as e:
            logger.warning(
                "WEEKLY pin failed channel=%s msg=%s: %s",
                channel["key"], sent.message_id, e,
            )

        data_utils.upsert_weekly_post(
            channel["key"], iso_week, channel["chat_id"], sent.message_id, content_hash,
        )
        logger.info(
            "WEEKLY published channel=%s week=%s msg=%s",
            channel["key"], iso_week, sent.message_id,
        )

        # Best-effort unpin previous week's message so only one weekly is pinned.
        prev = data_utils.get_last_weekly_post_for_channel(channel["key"], iso_week)
        # Compare as strings: weekly_posts.chat_id is TEXT (migration 014, to hold
        # @usernames), so a numeric channel comes back as "-100..." while CHANNELS
        # holds an int. == was always False for those, and the academy channel went
        # months accumulating one pinned weekly per week.
        if prev and str(prev["chat_id"]) == str(channel["chat_id"]):
            try:
                await bot.unpin_chat_message(
                    chat_id=channel["chat_id"], message_id=prev["message_id"],
                )
                logger.info(
                    "WEEKLY unpinned previous channel=%s week=%s msg=%s",
                    channel["key"], prev["iso_week"], prev["message_id"],
                )
            except Exception as e:
                logger.warning(
                    "WEEKLY unpin previous failed channel=%s msg=%s: %s",
                    channel["key"], prev["message_id"], e,
                )
        return

    # Existing weekly — only edit if content changed.
    if existing["content_hash"] == content_hash:
        return
    try:
        await bot.edit_message_text(
            chat_id=existing["chat_id"],
            message_id=existing["message_id"],
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        # Message may have been manually deleted by an admin; log and move on.
        # The hash is not updated so we'll try again next tick — and if the
        # message really is gone we'll keep failing until a human intervenes.
        if "not modified" not in str(e).lower():
            logger.warning(
                "WEEKLY edit failed channel=%s week=%s msg=%s: %s",
                channel["key"], iso_week, existing["message_id"], e,
            )
        return

    data_utils.upsert_weekly_post(
        channel["key"], iso_week, existing["chat_id"], existing["message_id"], content_hash,
    )
    logger.info(
        "WEEKLY updated channel=%s week=%s msg=%s",
        channel["key"], iso_week, existing["message_id"],
    )


async def refresh_all_weeklies(bot) -> None:
    """Iterate every configured channel — called from the periodic refresh loop."""
    for channel in CHANNELS:
        try:
            await maybe_publish_or_update_weekly(bot, channel)
        except Exception as e:
            logger.warning(
                "WEEKLY refresh failed channel=%s: %s", channel.get("key"), e,
            )
