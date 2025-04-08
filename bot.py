import os
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, ConversationHandler)
from deep_translator import GoogleTranslator
import re
import logging
from flask import Flask, request

# --- Налаштування логів ---
logging.basicConfig(level=logging.INFO)

# --- Flask сервер ---
app = Flask(__name__)

# --- Константи ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Наприклад: https://bot-name.onrender.com
PORT = int(os.environ.get("PORT", 8443))

LANGUAGE_SELECTION = range(1)
user_data_store = {}

LANGUAGES = {
    "Arabic 🇦🇪": "ar",
    "English 🇬🇧": "en",
    "Ukrainian 🇺🇦": "uk",
    "French 🇫🇷": "fr",
    "Spanish 🇪🇸": "es",
    "German 🇩🇪": "de"
}

# --- Парсинг SRT ---
def parse_srt(content):
    entries = []
    blocks = re.split(r"\n\n", content.strip())
    for block in blocks:
        lines = block.split("\n")
        if len(lines) >= 3:
            index = int(lines[0])
            timing = lines[1]
            text = " ".join(lines[2:])
            entries.append({"index": index, "timing": timing, "text": text})
    return entries

# --- Побудова SRT ---
def build_srt(entries):
    output = ""
    for e in entries:
        output += f"{e['index']}\n{e['timing']}\n{e['text']}\n\n"
    return output.strip()

# --- Обробка /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[KeyboardButton(lang)] for lang in LANGUAGES.keys()]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("👋 Обери мову перекладу:", reply_markup=markup)
    return LANGUAGE_SELECTION

# --- Вибір мови ---
async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.message.text
    if lang in LANGUAGES:
        chat_id = update.message.chat_id
        user_data_store[chat_id] = {"lang": LANGUAGES[lang]}
        await update.message.reply_text("📄 Надішли файл .srt для перекладу.")
        return ConversationHandler.END
    await update.message.reply_text("❌ Невірна мова. Спробуй ще раз.")
    return LANGUAGE_SELECTION

# --- Обробка файлу ---
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in user_data_store:
        await update.message.reply_text("🔁 Спочатку обери мову за допомогою /start")
        return

    file = await update.message.document.get_file()
    path = f"temp_{chat_id}.srt"
    await file.download_to_drive(path)
    logging.info(f"📥 Завантажено файл {path}")

    with open(path, "r", encoding="utf-8") as f:
        entries = parse_srt(f.read())

    translated = []
    for e in entries:
        try:
            translated_text = GoogleTranslator(source="auto", target=user_data_store[chat_id]['lang']).translate(e['text'])
            translated.append({"index": e['index'], "timing": e['timing'], "text": translated_text})
        except Exception as err:
            logging.warning(f"Помилка перекладу: {err}")

    result = build_srt(translated)
    result_path = f"translated_{chat_id}.srt"
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(result)

    await update.message.reply_document(InputFile(result_path))
    os.remove(path)
    os.remove(result_path)
    logging.info(f"✅ Переклад завершено та надіслано користувачу")

# --- Запуск застосунку ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    from telegram.ext import Application
    application = ApplicationBuilder().token(TOKEN).build()
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

if __name__ == "__main__":
    from telegram.ext import Application

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE_SELECTION: [MessageHandler(filters.TEXT, select_language)]
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Document.FILE_EXTENSION("srt"), handle_file))

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )
