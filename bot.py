
import os
import logging
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
from deep_translator import GoogleTranslator
from tempfile import NamedTemporaryFile

# Логування
logging.basicConfig(level=logging.INFO)

# Flask додаток
app = Flask(__name__)

# Глобальні змінні
user_files = {}
user_langs = {}

LANGUAGES = {
    "en": "English",
    "uk": "Ukrainian",
    "ar": "Arabic",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh-CN": "Chinese",
    "ja": "Japanese",
    "pl": "Polish",
    "ro": "Romanian",
    "tr": "Turkish",
    "nl": "Dutch"
}

# Обробник /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені .srt файл, і я перекладу його на обрані мови.")

# Обробка файлу
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("Будь ласка, надішли файл з розширенням .srt")
        return

    file = await context.bot.get_file(document.file_id)
    with NamedTemporaryFile(delete=False, suffix=".srt") as f:
        await file.download_to_drive(f.name)
        user_files[update.effective_user.id] = f.name

    keyboard = [
        [InlineKeyboardButton(LANGUAGES[code], callback_data=code)]
        for code in LANGUAGES
    ]
    keyboard.append([InlineKeyboardButton("✅ Переклад", callback_data="translate")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть мови перекладу:", reply_markup=reply_markup)
    user_langs[update.effective_user.id] = []

# Обробка натискань кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if query.data == "translate":
        if not user_langs.get(user_id):
            await query.edit_message_text("Ви не вибрали жодної мови.")
            return

        await query.edit_message_text(f"Починаю переклад на: {', '.join(user_langs[user_id])}")
        await translate_and_send(update, context, user_id)
    else:
        user_langs[user_id].append(query.data)

# Переклад і надсилання
async def translate_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    file_path = user_files.get(user_id)
    if not file_path:
        await context.bot.send_message(chat_id=user_id, text="Файл не знайдено.")
        return

    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    for lang in user_langs[user_id]:
        translated_lines = []
        for line in lines:
            if line.strip().isdigit() or "-->" in line or not line.strip():
                translated_lines.append(line)
            else:
                try:
                    translated = GoogleTranslator(source="auto", target=lang).translate(line.strip())
                    translated_lines.append(translated + "
")
                except Exception as e:
                    logging.error(f"Помилка перекладу: {e}")
                    translated_lines.append(line)

        output_path = f"{file_path}_{lang}.srt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(translated_lines)

        with open(output_path, "rb") as f:
            await context.bot.send_document(chat_id=user_id, document=f, filename=f"translated_{lang}.srt")

# Flask endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# Запуск бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not TOKEN or not WEBHOOK_URL:
    raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути задані як змінні середовища.")

application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
application.add_handler(CallbackQueryHandler(button))

if __name__ == "__main__":
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL,
    )
