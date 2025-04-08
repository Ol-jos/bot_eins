import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from deep_translator import GoogleTranslator

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Constants
TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# State management
user_states = {}

# Languages
LANGUAGES = {
    "uk": "Ukrainian",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "pl": "Polish",
    "nl": "Dutch",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh-CN": "Chinese",
    "tr": "Turkish",
    "ar": "Arabic"
}

# Telegram application
application = ApplicationBuilder().token(TOKEN).build()


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("👋 Надішліть .srt файл для перекладу.")


async def handle_file(update: Update, context: CallbackContext):
    document = update.message.document
    user_id = update.message.from_user.id

    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("⚠️ Будь ласка, надішліть файл із розширенням .srt")
        return

    file = await context.bot.get_file(document.file_id)
    content = await file.download_as_bytearray()
    user_states[user_id] = {"srt": content.decode("utf-8"), "langs": []}

    # Побудова клавіатури мов
    keyboard = [[InlineKeyboardButton(name, callback_data=code)] for code, name in LANGUAGES.items()]
    keyboard.append([InlineKeyboardButton("✅ Переклад", callback_data="translate")])

    await update.message.reply_text(
        "📍 Оберіть мови для перекладу:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if user_id not in user_states:
        await query.edit_message_text("⚠️ Спочатку надішліть .srt файл.")
        return

    if query.data == "translate":
        langs = user_states[user_id]["langs"]
        if not langs:
            await query.edit_message_text("❗ Ви не вибрали жодної мови.")
            return

        await query.edit_message_text(f"🔄 Починаю переклад на мови: {', '.join([LANGUAGES[l] for l in langs])}...")
        await translate_and_send(update, context, user_id)
    else:
        lang = query.data
        if lang not in user_states[user_id]["langs"]:
            user_states[user_id]["langs"].append(lang)


async def translate_and_send(update: Update, context: CallbackContext, user_id):
    original_srt = user_states[user_id]["srt"]
    langs = user_states[user_id]["langs"]

    for lang in langs:
        translated_lines = []
        for line in original_srt.split("\n"):
            if line.strip().isdigit() or "-->" in line or line.strip() == "":
                translated_lines.append(line)
            else:
                try:
                    translated = GoogleTranslator(source='auto', target=lang).translate(line)
                except Exception as e:
                    logger.error(f"Translation error: {e}")
                    translated = line
                translated_lines.append(translated)

        translated_text = "\n".join(translated_lines)

        with open(f"translated_{lang}.srt", "w", encoding="utf-8") as f:
            f.write(translated_text)

        with open(f"translated_{lang}.srt", "rb") as f:
            await context.bot.send_document(chat_id=user_id, document=f, filename=f"translated_{lang}.srt")

    del user_states[user_id]


# Flask webhook handler
@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "Bot is up and running"


if __name__ == "__main__":
    async def main():
        await application.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.Document.FILE_EXTENSION("srt"), handle_file))
        application.add_handler(CallbackQueryHandler(button_handler))

        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

    asyncio.run(main())
