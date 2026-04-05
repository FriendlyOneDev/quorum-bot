import os
import traceback
from datetime import datetime

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
from bot.handlers import (
    ping,
    cancel,
    help_cmd,
    # /create
    create_start, create_title, create_desc, create_max,
    create_date, create_time, create_image,
    CREATE_TITLE, CREATE_DESC, CREATE_MAX, CREATE_DATE, CREATE_TIME, CREATE_IMAGE,
    # /view
    view_games,
    # /edit
    edit_start, edit_select, edit_field, edit_value,
    EDIT_SELECT, EDIT_FIELD, EDIT_VALUE,
    # /delete
    delete_start, delete_select, delete_confirm,
    DELETE_SELECT, DELETE_CONFIRM,
    # /post + join/leave
    post_start, post_select,
    join_game, leave_game,
    # /rollcall
    rollcall_start, rollcall_select,
    # slots
    giveslot, giveslots, myslots,
    # roles
    setrole, whoami, users_list,
    # register
    register_start, register_callback,
)


load_dotenv()
api_key = os.getenv("TELEGRAM_TOKEN")
admin_id = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None


async def on_startup(app):
    # Run database migrations
    db.init_db()

    # One-time migration from old JSON format
    data_utils.migrate_from_events()

    # Seed admin user
    if admin_id:
        data_utils.get_or_create_user(admin_id)
        data_utils.set_role(admin_id, "admin")

        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await app.bot.send_message(
            chat_id=admin_id, text=f"Bot started successfully at {start_time}"
        )


async def error_handler(update, context):
    tb = traceback.format_exception(
        type(context.error), context.error, context.error.__traceback__
    )
    msg = f"Error:\n{''.join(tb)}"
    # Truncate to fit Telegram message limit
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
            CREATE_DATE: [CallbackQueryHandler(create_date, pattern=r"^cal:")],
            CREATE_TIME: [CallbackQueryHandler(create_time, pattern=r"^time:")],
            CREATE_IMAGE: [
                MessageHandler(filters.PHOTO, create_image),
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

    app.add_handler(create_conv)
    app.add_handler(edit_conv)
    app.add_handler(delete_conv)

    # Simple command handlers
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("view", view_games))
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
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("users", users_list))

    # Register command
    app.add_handler(CommandHandler("register", register_start))

    # Standalone callback handlers
    app.add_handler(CallbackQueryHandler(post_select, pattern=r"^post:"))
    app.add_handler(CallbackQueryHandler(rollcall_select, pattern=r"^rollcall:"))
    app.add_handler(CallbackQueryHandler(join_game, pattern=r"^join:"))
    app.add_handler(CallbackQueryHandler(leave_game, pattern=r"^leave:"))
    app.add_handler(CallbackQueryHandler(register_callback, pattern=r"^register_me$"))

    app.run_polling()
