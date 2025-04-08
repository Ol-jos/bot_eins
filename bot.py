import os
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from deep_translator import GoogleTranslator
from flask import Flask, request
import re

TOKEN = os.environ.get("TELEGRAM_TOKEN")
LANGUAGE_SELECTION = range(1)
user_data_store = {}

# --- Основні мови ---
LANGUAGES = {
    "Arabic 🇦�": "ar",
    "English 🇬🇧": "en",
    "Ukrainian 🇺🇦": "uk",
    "French 🇫🇷": "fr",
    "Spanish 🇪🇸": "es",
    "German 🇩🇪": "de",
    "Russian 🇷🇺": "ru",
    "Polish 🇵🇱": "pl",
    "Italian 🇮🇹": "it",
    "Portuguese 🇵🇹": "pt",
    "Turkish 🇹🇷": "tr",
    "Hindi 🇮🇳": "hi",
    "Japanese 🇯🇵": "ja",
    "Korean 🇰🇷": "ko",
    "Chinese 🇨🇳": "zh-CN"
}

# --- Команди ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(lang)] for lang in LANGUAGES.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Вибери мови, на які потрібно перекласти:", reply_markup=reply_markup)
    return LANGUAGE_SELECTION

async def select_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    selected_lang = update.message.text
    user_data_store[user_id] = LANGUAGES.get(selected_lang, "ar")
    await update.message.reply_text(f"Чекаю файл субтитрів .srt для перекладу на {selected_lang} 📂")
    return ConversationHandler.END

# --- Обробка файлу ---
def translate_line(line, target_lang):
    line = line.strip()
    if re.match(r"^\d+$", line) or re.match(r"^\d{2}:\d{2}:\d{2},\d{3}", line):
        return line
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(line)
    except:
        return line

def translate_srt(file_path, target_lang):
    translated_lines = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            translated_lines.append(translate_line(line, target_lang))
    return "\n".join(translated_lines)

async def handle_file_if_srt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if document and document.file_name.endswith(".srt"):
        await handle_file(update, context)
    else:
        await update.message.reply_text("Будь ласка, надішліть файл із розширенням .srt 📄")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    target_lang = user_data_store.get(user_id, "ar")

    file = await update.message.document.get_file()
    file_path = f"{user_id}.srt"
    await file.download_to_drive(file_path)

    translated_text = translate_srt(file_path, target_lang)
    translated_path = f"translated_{user_id}_{target_lang}.srt"
    with open(translated_path, "w", encoding="utf-8") as f:
        f.write(translated_text)

    await update.message.reply_document(InputFile(translated_path))
    os.remove(file_path)
    os.remove(translated_path)

# --- Запуск ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_languages)]
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Document.ALL & filters.ATTACHMENT, handle_file_if_srt))

    app.run_polling()
