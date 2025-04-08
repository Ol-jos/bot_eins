import os
import re
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, Document
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, ConversationHandler)
from deep_translator import GoogleTranslator

app = Flask(__name__)

LANGUAGES = {
    "Arabic 🇸🇮": "ar",
    "Chinese 🇨🇳": "zh",
    "English 🇬🇧": "en",
    "French 🇫🇷": "fr",
    "German 🇩🇪": "de",
    "Hindi 🇮🇳": "hi",
    "Italian 🇮🇹": "it",
    "Japanese 🇯🇵": "ja",
    "Korean 🇰🇷": "ko",
    "Polish 🇵🇱": "pl",
    "Portuguese 🇵🇹": "pt",
    "Russian 🇷🇺": "ru",
    "Spanish 🇪🇸": "es",
    "Turkish 🇹🇷": "tr",
    "Ukrainian 🇺🇦": "uk",
}

LANGUAGE_SELECTION = range(1)
user_data_store = {}

@app.route('/')
def index():
    return "Bot is running."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = ReplyKeyboardMarkup([[lang] for lang in LANGUAGES.keys()], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "🌐 Please choose your target language:",
        reply_markup=reply_markup
    )
    return LANGUAGE_SELECTION

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = update.message.text
    if language not in LANGUAGES:
        await update.message.reply_text("❌ Invalid language. Please choose from the keyboard.")
        return LANGUAGE_SELECTION

    user_data_store[update.effective_user.id] = LANGUAGES[language]
    await update.message.reply_text("✅ Language selected! Now send me the .srt file.")
    return ConversationHandler.END

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    target_lang = user_data_store.get(user_id)

    document = update.message.document
    if not document or not document.file_name.endswith(".srt"):
        await update.message.reply_text("⚠️ Надішли файл у форматі .srt")
        return

    file = await context.bot.get_file(document.file_id)
    srt_content = await file.download_as_bytearray()
    srt_text = srt_content.decode('utf-8')

    translated_text = translate_srt(srt_text, target_lang)
    with open("translated.srt", "w", encoding="utf-8") as f:
        f.write(translated_text)

    await update.message.reply_document(document=open("translated.srt", "rb"))
    os.remove("translated.srt")


def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except:
        return text  # fallback у разі помилки

def translate_srt(srt_text, target_lang):
    blocks = re.split(r'\n\n', srt_text)
    translated = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            index = lines[0]
            timing = lines[1]
            text_lines = lines[2:]
            translated_lines = [translate_text(line, target_lang) for line in text_lines]
            translated_block = f"{index}\n{timing}\n" + "\n".join(translated_lines)
            translated.append(translated_block)
    return "\n\n".join(translated)

if __name__ == '__main__':
    from telegram.ext import ApplicationBuilder

    TOKEN = os.getenv("BOT_TOKEN")
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_language)]
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    application.run_polling()
