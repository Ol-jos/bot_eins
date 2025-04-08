import os
import logging
from flask import Flask, request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from deep_translator import GoogleTranslator
import tempfile

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
user_data = {}

LANGUAGES = {
    "en": "Англійська",
    "uk": "Українська",
    "de": "Німецька",
    "fr": "Французька",
    "it": "Італійська",
    "es": "Іспанська",
    "pl": "Польська",
    "tr": "Турецька",
    "pt": "Португальська",
    "ru": "Російська",
    "ja": "Японська",
    "zh-CN": "Китайська",
    "ar": "Арабська",
    "ko": "Корейська",
    "cs": "Чеська",
}

def is_valid_srt(filename: str) -> bool:
    return filename.lower().endswith(".srt")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Спершу надішли мені файл із субтитрами .srt")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    document = update.message.document

    if not is_valid_srt(document.file_name):
        await update.message.reply_text("Будь ласка, надішли файл із розширенням .srt.")
        return

    file = await context.bot.get_file(document.file_id)
    file_path = tempfile.mktemp(suffix=".srt")
    await file.download_to_drive(file_path)

    with open(file_path, encoding="utf-8") as f:
        context.user_data["original_srt"] = f.read()
        context.user_data["file_name"] = document.file_name

    context.user_data["languages"] = set()

    keyboard = [
        [InlineKeyboardButton(name, callback_data=code)] for code, name in LANGUAGES.items()
    ]
    keyboard.append([InlineKeyboardButton("🚀 Переклад", callback_data="translate")])

    await update.message.reply_text("Оберіть мови перекладу:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang_code = query.data

    if lang_code == "translate":
        selected_langs = context.user_data.get("languages", set())
        if not selected_langs:
            await query.edit_message_text("Ви не обрали жодної мови. Будь ласка, оберіть хоча б одну.")
            return

        await query.edit_message_text(f"Починаємо переклад на: {', '.join([LANGUAGES[code] for code in selected_langs])}")
        await translate_and_send(update, context)
        return

    context.user_data["languages"].add(lang_code)
    await query.answer(f"✅ {LANGUAGES[lang_code]} обрано")

async def translate_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    original_srt = context.user_data.get("original_srt", "")
    file_name = context.user_data.get("file_name", "translated.srt")
    langs = context.user_data.get("languages", set())

    for lang in langs:
        translated_lines = []
        for line in original_srt.splitlines():
            try:
                translated = GoogleTranslator(source="auto", target=lang).translate(line)
            except Exception:
                translated = line
            translated_lines.append(translated)

        temp_path = tempfile.mktemp(suffix=f"_{lang}.srt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write("\n".join(translated_lines))

        await context.bot.send_document(chat_id=user_id, document=InputFile(temp_path, filename=f"{lang}_{file_name}"))

    await context.bot.send_message(chat_id=user_id, text="✅ Переклад завершено!")

async def webhook_view(request):
    if request.method == "POST":
        await application.update_queue.put(Update.de_json(await request.get_json(force=True), application.bot))
    return "ok"

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
application.add_handler(CallbackQueryHandler(handle_language_selection))

if __name__ == "__main__":
    if not TOKEN or not WEBHOOK_URL:
        raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути задані як змінні середовища.")

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL,
    )
