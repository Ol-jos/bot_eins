import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)
from deep_translator import GoogleTranslator

# --- Logging ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- Flask App for Webhook ---
app = Flask(__name__)

# --- Telegram Bot ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

application = Application.builder().token(TOKEN).build()

# --- Globals ---
user_data = {}

# --- Handlers ---
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("👋 Надішли мені .srt файл для перекладу.")

async def handle_file(update: Update, context: CallbackContext):
    document = update.message.document

    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("❌ Це не .srt файл. Надішли коректний файл субтитрів.")
        return

    user_id = update.message.from_user.id
    user_data[user_id] = {"file": document, "languages": []}

    keyboard = [
        [InlineKeyboardButton("🇺🇸 Англійська", callback_data="en"),
         InlineKeyboardButton("🇺🇦 Українська", callback_data="uk"),
         InlineKeyboardButton("🇩🇪 Німецька", callback_data="de")],
        [InlineKeyboardButton("🇫🇷 Французька", callback_data="fr"),
         InlineKeyboardButton("🇪🇸 Іспанська", callback_data="es"),
         InlineKeyboardButton("🇨🇳 Китайська", callback_data="zh-CN")],
        [InlineKeyboardButton("✅ Почати переклад", callback_data="start_translation")]
    ]

    await update.message.reply_text("🔤 Обери мови для перекладу:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_language_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = user_data.get(user_id)

    if not data:
        await query.edit_message_text("⚠️ Спочатку надішли .srt файл.")
        return

    lang_code = query.data

    if lang_code == "start_translation":
        if not data["languages"]:
            await query.edit_message_text("❗ Ти не обрав жодної мови.")
            return

        await query.edit_message_text("🔄 Починаю переклад на мови: " + ", ".join(data["languages"]))
        await start_translation(update, context, data)
        return

    if lang_code not in data["languages"]:
        data["languages"].append(lang_code)

async def start_translation(update: Update, context: CallbackContext, data):
    file = await data["file"].get_file()
    file_content = await file.download_as_bytearray()
    lines = file_content.decode("utf-8").splitlines()

    translated_versions = {}

    for lang in data["languages"]:
        translated_lines = []
        for line in lines:
            if line.strip().isdigit() or "-->" in line or not line.strip():
                translated_lines.append(line)
            else:
                try:
                    translated = GoogleTranslator(source='auto', target=lang).translate(line)
                except Exception:
                    translated = "[ПОМИЛКА ПЕРЕКЛАДУ]"
                translated_lines.append(translated)
        translated_versions[lang] = "\n".join(translated_lines)

    for lang_code, content in translated_versions.items():
        filename = f"translated_{lang_code}.srt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(filename, "rb"))

# --- Telegram Webhook Endpoint ---
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
        return "ok"
    return "not allowed", 403

# --- Register Handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
application.add_handler(CallbackQueryHandler(handle_language_selection))

# --- Run ---
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=PORT)
