from telegram.ext import ApplicationBuilder, CommandHandler
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
from datetime import datetime
import os

from bot.handlers import ping, create_event, view_events, edit_event, delete_event, rollcall


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

    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("create", create_event))
    app.add_handler(CommandHandler("view", view_events))
    app.add_handler(CommandHandler("edit", edit_event))
    app.add_handler(CommandHandler("delete", delete_event))
    app.add_handler(CommandHandler("rollcall", rollcall))

    app.run_polling()
