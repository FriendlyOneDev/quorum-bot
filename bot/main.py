import asyncio
import logging
import os
import traceback
from datetime import datetime

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest
from dotenv import load_dotenv

import db
import data_utils
from bot.config import REFRESH_INTERVAL_MINUTES
from bot.handlers import (
    ping,
    cancel,
    help_cmd,
    # /create
    create_start, create_title, create_desc, create_max, create_location,
    create_date, create_time, create_tone, create_image,
    CREATE_TITLE, CREATE_DESC, CREATE_MAX, CREATE_LOCATION, CREATE_DATE, CREATE_TIME, CREATE_TONE, CREATE_IMAGE,
    # /view
    view_games,
    # /edit
    edit_start, edit_select, edit_field, edit_value,
    EDIT_SELECT, EDIT_FIELD, EDIT_VALUE,
    # /delete
    delete_start, delete_select, delete_confirm,
    DELETE_SELECT, DELETE_CONFIRM,
    # /kick
    kick_start, kick_select_game, kick_select_player,
    KICK_SELECT_GAME, KICK_SELECT_PLAYER,
    # /post + join/leave + publish
    post_start, post_select,
    publish_now_callback, publish_skip_callback,
    join_game, leave_game, signup_toggle, interested_toggle,
    maybe_fire_24h_notifications,
    # browse
    available_games, my_games,
    # /rollcall
    rollcall_start, rollcall_select,
    # slots
    giveslot, giveslots, myslots,
    # roles
    setrole, setname, whoami, users_list, toggle_notify, toggle_bypass,
    # register
    register_start, register_callback,
)


load_dotenv()
api_key = os.getenv("TELEGRAM_TOKEN")
admin_id = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None


logger = logging.getLogger(__name__)


async def _refresh_all_posts(bot):
    from bot.handlers.post import update_posted_message
    games = data_utils.get_all_games()
    refreshed = 0
    for game in games:
        if game.get("message_id"):
            try:
                await update_posted_message(bot, game, game["game_id"])
                refreshed += 1
            except Exception as e:
                logger.warning("REFRESH failed game=%s: %s", game["game_id"], e)
        try:
            await maybe_fire_24h_notifications(bot, game)
        except Exception as e:
            logger.warning("24H_NOTIFY failed game=%s: %s", game["game_id"], e)
    logger.info("REFRESH cycle complete: %d games refreshed", refreshed)


async def _periodic_refresh(bot):
    interval = REFRESH_INTERVAL_MINUTES * 60
    while True:
        await asyncio.sleep(interval)
        await _refresh_all_posts(bot)


async def on_startup(app):
    # Run database migrations
    db.init_db()

    # One-time migration from old JSON format
    data_utils.migrate_from_events()

    # Refresh all posted game announcements
    await _refresh_all_posts(app.bot)

    # Start periodic refresh task
    asyncio.create_task(_periodic_refresh(app.bot))

    # Seed admin user
    if admin_id:
        data_utils.get_or_create_user(admin_id)
        data_utils.set_role(admin_id, "admin")

        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await app.bot.send_message(
            chat_id=admin_id, text=f"Bot started successfully at {start_time}"
        )


_network_error_times: list[float] = []
_last_network_alert: float = 0.0
NETWORK_ERROR_WINDOW = 300  # 5 minutes
NETWORK_ERROR_THRESHOLD = 5  # alert if N+ errors in window
NETWORK_ALERT_COOLDOWN = 1800  # don't re-alert for 30 minutes


async def error_handler(update, context):
    import time
    err = context.error

    # Filter out transient network/DNS errors but track frequency
    import httpx
    from telegram.error import NetworkError, TimedOut
    if isinstance(err, (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError,
                        httpx.PoolTimeout, NetworkError, TimedOut)):
        logger.warning("Transient network error: %s", err)

        global _last_network_alert
        now = time.time()
        _network_error_times.append(now)
        # Prune old timestamps
        cutoff = now - NETWORK_ERROR_WINDOW
        _network_error_times[:] = [t for t in _network_error_times if t >= cutoff]

        if (len(_network_error_times) >= NETWORK_ERROR_THRESHOLD
                and now - _last_network_alert > NETWORK_ALERT_COOLDOWN
                and admin_id):
            _last_network_alert = now
            count = len(_network_error_times)
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ {count} network errors in last {NETWORK_ERROR_WINDOW // 60} min. Last: {err}",
                )
            except Exception:
                pass
        return

    tb = traceback.format_exception(type(err), err, err.__traceback__)
    msg = f"Error:\n{''.join(tb)}"
    if len(msg) > 4000:
        msg = msg[:4000] + "\n... (truncated)"

    if admin_id:
        try:
            await context.bot.send_message(chat_id=admin_id, text=msg)
        except Exception:
            pass


if __name__ == "__main__":
    request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=10.0,
        media_write_timeout=60.0,
    )

    app = (
        ApplicationBuilder()
        .token(api_key)
        .request(request)
        .post_init(on_startup)
        .build()
    )

    # Error handler
    app.add_error_handler(error_handler)

    # Conversation handlers
    create_conv = ConversationHandler(
        entry_points=[CommandHandler("create", create_start)],
        states={
            CREATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_title)],
            CREATE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_desc)],
            CREATE_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_max)],
            CREATE_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_location)],
            CREATE_DATE: [CallbackQueryHandler(create_date, pattern=r"^cal:")],
            CREATE_TIME: [CallbackQueryHandler(create_time, pattern=r"^time:")],
            CREATE_TONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_tone)],
            CREATE_IMAGE: [
                MessageHandler(filters.PHOTO | filters.ANIMATION, create_image),
                CommandHandler("skip", create_image),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    edit_conv = ConversationHandler(
        entry_points=[CommandHandler("edit", edit_start)],
        states={
            EDIT_SELECT: [CallbackQueryHandler(edit_select, pattern=r"^edit_sel:")],
            EDIT_FIELD: [CallbackQueryHandler(edit_field, pattern=r"^edit_field:")],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=r"^cancel$"),
        ],
    )

    delete_conv = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start)],
        states={
            DELETE_SELECT: [CallbackQueryHandler(delete_select, pattern=r"^del_sel:")],
            DELETE_CONFIRM: [CallbackQueryHandler(delete_confirm, pattern=r"^del_(yes|no)")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=r"^cancel$"),
        ],
    )

    kick_conv = ConversationHandler(
        entry_points=[CommandHandler("kick", kick_start)],
        states={
            KICK_SELECT_GAME: [CallbackQueryHandler(kick_select_game, pattern=r"^kick_game:")],
            KICK_SELECT_PLAYER: [CallbackQueryHandler(kick_select_player, pattern=r"^kick_player:")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=r"^cancel$"),
        ],
    )

    app.add_handler(create_conv)
    app.add_handler(edit_conv)
    app.add_handler(delete_conv)
    app.add_handler(kick_conv)

    # Simple command handlers
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("view", view_games))
    app.add_handler(CommandHandler("games", available_games))
    app.add_handler(CommandHandler("mygames", my_games))
    app.add_handler(CommandHandler("post", post_start))
    app.add_handler(CommandHandler("rollcall", rollcall_start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("start", help_cmd))

    # Slot commands
    app.add_handler(CommandHandler("giveslot", giveslot))
    app.add_handler(CommandHandler("giveslots", giveslots))
    app.add_handler(CommandHandler("myslots", myslots))

    # Role commands
    app.add_handler(CommandHandler("setrole", setrole))
    app.add_handler(CommandHandler("setname", setname))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("users", users_list))
    app.add_handler(CommandHandler("togglenotify", toggle_notify))
    app.add_handler(CommandHandler("togglebypass", toggle_bypass))

    # Register command
    app.add_handler(CommandHandler("register", register_start))

    # Standalone callback handlers
    app.add_handler(CallbackQueryHandler(post_select, pattern=r"^post:"))
    app.add_handler(CallbackQueryHandler(publish_now_callback, pattern=r"^publish_now:"))
    app.add_handler(CallbackQueryHandler(publish_skip_callback, pattern=r"^publish_skip$"))
    app.add_handler(CallbackQueryHandler(rollcall_select, pattern=r"^rollcall:"))
    app.add_handler(CallbackQueryHandler(signup_toggle, pattern=r"^signup:"))
    app.add_handler(CallbackQueryHandler(interested_toggle, pattern=r"^interested:"))
    app.add_handler(CallbackQueryHandler(join_game, pattern=r"^join:"))
    app.add_handler(CallbackQueryHandler(leave_game, pattern=r"^leave:"))
    app.add_handler(CallbackQueryHandler(register_callback, pattern=r"^register_me$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern=r"^cancel$"))

    app.run_polling(allowed_updates=["message", "callback_query"])
