import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, CommandHandler, filters)
from deep_translator import GoogleTranslator
from flask import Flask, request
import tempfile

# Логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask для вебхуку
app = Flask(__name__)

# Пам'ять для збереження файлів і вибраних мов
user_data = {}

# Список мов
LANGUAGES = {
    "🇬🇧 English": "en",
    "🇺🇦 Українська": "uk",
    "🇫🇷 Français": "fr",
    "🇩🇪 Deutsch": "de",
    "🇪🇸 Español": "es",
    "🇮🇹 Italiano": "it",
    "🇵🇱 Polski": "pl",
    "🇹🇷 Türkçe": "tr",
    "🇷🇴 Română": "ro",
    "🇳🇱 Nederlands": "nl",
    "🇵🇹 Português": "pt",
    "🇸🇪 Svenska": "sv",
    "🇳🇴 Norsk": "no",
    "🇨🇳 中文": "zh-CN",
    "🇯🇵 日本語": "ja"
}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Надішли мені .srt файл для перекладу.")

# Обробка документа
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document.file_name.endswith(".srt"):
        await update.message.reply_text("❌ Потрібен .srt файл.")
        return

    user_id = update.message.from_user.id
    user_data[user_id] = {"file": None, "languages": []}

    file = await update.message.document.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".srt") as f:
        await file.download_to_drive(f.name)
        user_data[user_id]["file"] = f.name

    await show_language_buttons(update, context)

# Показати кнопки мов
async def show_language_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(name, callback_data=code)] for name, code in LANGUAGES.items()
    ]
    keyboard.append([InlineKeyboardButton("✅ Переклад", callback_data="translate")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть мови для перекладу:", reply_markup=reply_markup)

# Обробка натискання кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data:
        await query.edit_message_text("⚠️ Спершу надішліть .srt файл!")
        return

    if query.data == "translate":
        if not user_data[user_id]["languages"]:
            await query.edit_message_text("⚠️ Ви не обрали жодної мови.")
            return
        await query.edit_message_text("🔄 Переклад почався на мови: " + ", ".join(user_data[user_id]["languages"]))
        await translate_file(update, context, user_id)
        return

    if query.data not in user_data[user_id]["languages"]:
        user_data[user_id]["languages"].append(query.data)

# Переклад файлу
async def translate_file(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    path = user_data[user_id]["file"]
    with open(path, "r", encoding="utf-8") as f:
        content = f.readlines()

    for lang_code in user_data[user_id]["languages"]:
        translated = []
        for line in content:
            try:
                translated.append(GoogleTranslator(source='auto', target=lang_code).translate(text=line.strip()) + "\n")
            except Exception:
                translated.append(line)

        out_path = path.replace(".srt", f"_{lang_code}.srt")
        with open(out_path, "w", encoding="utf-8") as out:
            out.writelines(translated)

        with open(out_path, "rb") as doc:
            await context.bot.send_document(chat_id=user_id, document=doc, filename=os.path.basename(out_path))

# Flask-ендпоінт
@app.route('/webhook', methods=["POST"])
def webhook():
    from telegram import Update
    from telegram.ext import Application
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.process_update(update)
    return "ok"

# Глобальна змінна application
TOKEN = os.getenv("TELEGRAM_TOKEN")
application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.FILE_EXTENSION("srt"), handle_file))
application.add_handler(CallbackQueryHandler(button_handler))

# Webhook запуск
if __name__ == "__main__":
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")

    if not TOKEN or not WEBHOOK_URL:
        raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути задані як змінні середовища.")

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL
    )
