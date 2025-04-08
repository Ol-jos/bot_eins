import os
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, CallbackContext, filters
)
from deep_translator import GoogleTranslator
import logging
import re

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- States ---
LANGUAGE_SELECTION, CONFIRM_TRANSLATION = range(2)

# --- Languages ---
LANGUAGES = {
    "English 🇬🇧": "en",
    "Ukrainian 🇺🇦": "uk",
    "French 🇫🇷": "fr",
    "Spanish 🇪🇸": "es",
    "German 🇩🇪": "de",
    "Polish 🇵🇱": "pl",
    "Italian 🇮🇹": "it",
    "Dutch 🇳🇱": "nl",
    "Portuguese 🇵🇹": "pt",
    "Russian 🇷🇺": "ru",
    "Chinese 🇨🇳": "zh-CN",
    "Arabic 🇸🇦": "ar",
    "Turkish 🇹🇷": "tr",
    "Japanese 🇯🇵": "ja",
    "Korean 🇰🇷": "ko"
}

user_data_store = {}

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Надішли мені .srt файл із субтитрами для перекладу.")
    return LANGUAGE_SELECTION

# --- Handle File ---
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("⚠️ Потрібен файл у форматі .srt. Спробуй ще раз.")
        return LANGUAGE_SELECTION

    user_id = update.message.from_user.id
    file = await context.bot.get_file(document.file_id)
    file_path = f"{user_id}_original.srt"
    await file.download_to_drive(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        user_data_store[user_id] = {"original": f.read(), "languages": []}

    keyboard = [[KeyboardButton(lang)] for lang in LANGUAGES.keys()] + [[KeyboardButton("✅ Переклад!")]]
    await update.message.reply_text("🔤 Обери мови для перекладу:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CONFIRM_TRANSLATION

# --- Handle Language Selection ---
async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if text == "✅ Переклад!":
        langs = user_data_store[user_id].get("languages", [])
        if not langs:
            await update.message.reply_text("⚠️ Спочатку обери хоча б одну мову!")
            return CONFIRM_TRANSLATION

        await update.message.reply_text(f"⏳ Розпочинаю переклад на: {', '.join(langs)}")
        await translate_subtitles(update, context)
        return ConversationHandler.END

    if text in LANGUAGES:
        code = LANGUAGES[text]
        if code not in user_data_store[user_id]["languages"]:
            user_data_store[user_id]["languages"].append(code)
            await update.message.reply_text(f"✅ Додано: {text}")
        else:
            await update.message.reply_text(f"⚠️ Мову вже додано: {text}")
    else:
        await update.message.reply_text("⛔ Невідома мова. Обери зі списку або натисни 'Переклад!'")

    return CONFIRM_TRANSLATION

# --- Переклад ---
async def translate_subtitles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    original_text = user_data_store[user_id]["original"]
    languages = user_data_store[user_id]["languages"]

    entries = re.findall(r'(\d+\n\d{2}:\d{2}:\d{2},\d{3} --> .*?\n)(.*?)(?=\n\n|\Z)', original_text, re.DOTALL)

    for lang in languages:
        translated_blocks = []
        for index, (timing, content) in enumerate(entries):
            try:
                translated_text = GoogleTranslator(source='auto', target=lang).translate(text=content.strip())
                block = f"{index + 1}\n{timing}{translated_text}\n"
                translated_blocks.append(block)
            except Exception as e:
                logging.warning(f"Помилка при перекладі: {e}")

        translated_file = f"{user_id}_{lang}.srt"
        with open(translated_file, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(translated_blocks))

        await context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(translated_file))

# --- Основна функція ---
if __name__ == '__main__':
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        raise ValueError("🚨 TELEGRAM_TOKEN не встановлено у середовищі!")

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE_SELECTION: [MessageHandler(filters.Document.ALL, handle_file)],
            CONFIRM_TRANSLATION: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_language)]
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.run_polling()
