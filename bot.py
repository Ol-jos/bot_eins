import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# Змінні середовища
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Перевірка наявності токена та вебхука
if not TOKEN or not WEBHOOK_URL:
    raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути задані як змінні середовища.")

# Ініціалізація Flask і Telegram Application
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()


# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені файл .srt для перекладу.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отримав ваше повідомлення!")

# Додавання обробників
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


# === ROUTE для Webhook ===
@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook endpoint для Telegram"""
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200


# === FLASK + PTB запуск ===
if __name__ == "__main__":
    import asyncio

    # Встановлення webhook
    asyncio.run(application.bot.set_webhook(url=WEBHOOK_URL))

    # Запуск Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
