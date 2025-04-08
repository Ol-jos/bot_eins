import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from deep_translator import GoogleTranslator

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Список мов для перекладу
LANGUAGES = [
    "en", "de", "fr", "es", "it", "uk", "pl", "ru", "tr", "nl",
    "pt", "ro", "ja", "ko", "zh-CN"
]
LANG_NAMES = {
    "en": "English", "de": "Deutsch", "fr": "Français", "es": "Español", "it": "Italiano",
    "uk": "Українська", "pl": "Polski", "ru": "Русский", "tr": "Türkçe", "nl": "Nederlands",
    "pt": "Português", "ro": "Română", "ja": "日本語", "ko": "한국어", "zh-CN": "中文"
}

# Глобальні змінні для збереження стану
user_files = {}
user_langs = {}

# Хендлер старту
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Надішліть .srt файл для перекладу.")

# Перевірка та обробка файлу
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("❌ Надішліть файл формату .srt")
        return

    file = update.message.document
    if not file.file_name.endswith(".srt"):
        await update.message.reply_text("❌ Потрібен файл з розширенням .srt")
        return

    file_id = file.file_id
    user_id = update.message.from_user.id
    user_files[user_id] = file_id
    user_langs[user_id] = []

    # Відображаємо кнопки мов
    keyboard = [[InlineKeyboardButton(LANG_NAMES[code], callback_data=code)] for code in LANGUAGES]
    keyboard.append([InlineKeyboardButton("✅ Переклад", callback_data="translate")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть мови перекладу:", reply_markup=reply_markup)

# Обробка натискань на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if user_id not in user_files:
        await query.edit_message_text("❌ Спочатку надішліть файл .srt")
        return

    if data == "translate":
        if not user_langs[user_id]:
            await query.edit_message_text("❌ Спочатку оберіть мови.")
            return

        await query.edit_message_text(f"🛠️ Розпочато переклад на мови: {', '.join(user_langs[user_id])}.")
        await perform_translation(query, context)
    else:
        if data not in user_langs[user_id]:
            user_langs[user_id].append(data)
        await query.answer(f"✅ Додано: {LANG_NAMES[data]}")

# Функція перекладу
async def perform_translation(query, context):
    user_id = query.from_user.id
    file_id = user_files[user_id]
    langs = user_langs[user_id]

    new_file = await context.bot.get_file(file_id)
    srt_content = await new_file.download_as_bytearray()
    lines = srt_content.decode("utf-8").splitlines()

    for lang in langs:
        translated_lines = []
        for line in lines:
            if line.strip().isdigit() or "-->" in line or line.strip() == "":
                translated_lines.append(line)
            else:
                try:
                    translated = GoogleTranslator(source='auto', target=lang).translate(line)
                    translated_lines.append(translated)
                except Exception as e:
                    translated_lines.append(line)
                    logger.error(f"Translation error: {e}")

        output = "\n".join(translated_lines)
        file_path = f"translated_{lang}.srt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(output)
        with open(file_path, "rb") as f:
            await context.bot.send_document(chat_id=user_id, document=f)

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

# Ініціалізація бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN or not WEBHOOK_URL:
    raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути задані як змінні середовища.")

application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.MIME_TYPE("application/x-subrip"), handle_file))
application.add_handler(CallbackQueryHandler(button_handler))

if __name__ == "__main__":
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL,
    )
