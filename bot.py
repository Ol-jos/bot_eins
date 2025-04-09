import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Налаштування логів
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Токен та URL
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Перевірка змінних середовища
if not TOKEN or not WEBHOOK_URL:
    raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути задані як змінні середовища.")

# Telegram bot
application = Application.builder().token(TOKEN).build()

# === Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Надішли мені .srt файл для перекладу.")

application.add_handler(CommandHandler("start", start))

# === Webhook route ===
@app.route("/webhook", methods=["POST"])
def webhook() -> tuple[str, int]:
    """Обробник Telegram оновлень через webhook"""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
        logger.info("✅ Update received and queued.")
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return "error", 500
    return "ok", 200

# === Flask launcher ===
if __name__ == "__main__":
    import asyncio

    async def main():
        logger.info("🚀 Installing webhook...")
        await application.bot.set_webhook(WEBHOOK_URL)
        logger.info("✅ Webhook set successfully.")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

    asyncio.run(main())
