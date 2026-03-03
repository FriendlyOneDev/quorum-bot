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
from datetime import datetime
import os

from bot.handlers import (
    ping,
    cancel,
    # /create
    create_start,
    create_title,
    create_desc,
    create_max,
    create_date,
    create_time,
    create_image,
    CREATE_TITLE,
    CREATE_DESC,
    CREATE_MAX,
    CREATE_DATE,
    CREATE_TIME,
    CREATE_IMAGE,
    # /view
    view_events,
    # /edit
    edit_start,
    edit_select,
    edit_field,
    edit_value,
    EDIT_SELECT,
    EDIT_FIELD,
    EDIT_VALUE,
    # /delete
    delete_start,
    delete_select,
    delete_confirm,
    DELETE_SELECT,
    DELETE_CONFIRM,
    # /post + join/leave
    post_start,
    post_select,
    join_event,
    leave_event,
    # /rollcall
    rollcall_start,
    rollcall_select,
)


# Load environment variables
load_dotenv()
api_key = os.getenv("TELEGRAM_TOKEN")
admin_id = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None


async def on_startup(app):
    if admin_id:
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await app.bot.send_message(
            chat_id=admin_id, text=f"Bot started successfully at {start_time}"
        )


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

    # Conversation handlers
    create_conv = ConversationHandler(
        entry_points=[CommandHandler("create", create_start)],
        states={
            CREATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_title)],
            CREATE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_desc)],
            CREATE_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_max)],
            CREATE_DATE: [
                CallbackQueryHandler(create_date, pattern=r"^cal:"),
            ],
            CREATE_TIME: [
                CallbackQueryHandler(create_time, pattern=r"^time:"),
            ],
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
    app.add_handler(CommandHandler("view", view_events))
    app.add_handler(CommandHandler("post", post_start))
    app.add_handler(CommandHandler("rollcall", rollcall_start))

    # Standalone callback handlers
    app.add_handler(CallbackQueryHandler(post_select, pattern=r"^post:"))
    app.add_handler(CallbackQueryHandler(rollcall_select, pattern=r"^rollcall:"))
    app.add_handler(CallbackQueryHandler(join_event, pattern=r"^join:"))
    app.add_handler(CallbackQueryHandler(leave_event, pattern=r"^leave:"))

    app.run_polling()
