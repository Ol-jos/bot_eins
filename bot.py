import os
from flask import Flask, request
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, ConversationHandler)
from deep_translator import GoogleTranslator
import re

TOKEN = os.environ.get("TELEGRAM_TOKEN")
LANGUAGE_SELECTION = range(1)
user_data_store = {}

LANGUAGES = {
    "Arabic \ud83c\udde6\ud83c\ueeae": "ar",
    "Chinese \ud83c\udde8\ud83c\uddf3": "zh-CN",
    "English \ud83c\uddec\ud83c\udde7": "en",
    "French \ud83c\uddeb\ud83c\uddf7": "fr",
    "German \ud83c\udde9\ud83c\uddea": "de",
    "Hindi \ud83c\uddee\ud83c\uddf3": "hi",
    "Italian \ud83c\uddee\ud83c\uddf9": "it",
    "Japanese \ud83c\uddef\ud83c\uddf5": "ja",
    "Korean \ud83c\uddf0\ud83c\uddf7": "ko",
    "Polish \ud83c\uddf5\ud83c\uddf1": "pl",
    "Portuguese \ud83c\uddf5\ud83c\uddf9": "pt",
    "Russian \ud83c\uddf7\ud83c\uddfa": "ru",
    "Spanish \ud83c\uddea\ud83c\uddf8": "es",
    "Turkish \ud83c\uddf9\ud83c\uddf7": "tr",
    "Ukrainian \ud83c\uddfa\ud83c\udde6": "uk"
}

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_chat.id] = []
    keyboard = []
    row = []
    for i, lang in enumerate(LANGUAGES.keys(), 1):
        row.append(KeyboardButton(lang))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton("\ud83d\udd70 \u041f\u043e\u0447\u0430\u0442\u0438 \u043f\u0435\u0440\u0435\u043a\u043b\u0430\u0434")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("\u041e\u0431\u0435\u0440\u0438 \u043c\u043e\u0432\u0438 \u0434\u043b\u044f \u043f\u0435\u0440\u0435\u043a\u043b\u0430\u0434\u0443:", reply_markup=reply_markup)
    return LANGUAGE_SELECTION

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    text = update.message.text

    if text == "\ud83d\udd70 \u041f\u043e\u0447\u0430\u0442\u0438 \u043f\u0435\u0440\u0435\u043a\u043b\u0430\u0434":
        await update.message.reply_text("\u0422\u0435\u043f\u0435\u0440 \u043d\u0430\u0434\u0441\u0438\u043b\u044c SRT-\u0444\u0430\u0439\u043b ")
        return ConversationHandler.END

    if text in LANGUAGES:
        user_data_store[user_id].append(LANGUAGES[text])
        await update.message.reply_text(f"\u0414\u043e\u0434\u0430\u043d\u043e: {text}")
    else:
        await update.message.reply_text("\u041d\u0435\u0432\u0456\u0434\u043e\u043c\u0430 \u043c\u043e\u0432\u0430. \u0421\u043f\u0440\u043e\u0431\u0443\u0439 \u0449\u0435 \u0440\u0430\u0437.")
    return LANGUAGE_SELECTION

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    languages = user_data_store.get(user_id)
    if not languages:
        await update.message.reply_text("\u0421\u043f\u043e\u0447\u0430\u0442\u043a\u0443 \u043e\u0431\u0435\u0440\u0438 \u043c\u043e\u0432\u0438 \u0442\u0430 \u043d\u0430\u0442\u0438\u0441\u043d\u0438 \u043a\u043d\u043e\u043f\u043a\u0443 \u201c\u041f\u043e\u0447\u0430\u0442\u0438 \u043f\u0435\u0440\u0435\u043a\u043b\u0430\u0434\u201d")
        return

    file = await update.message.document.get_file()
    file_path = f"/tmp/{file.file_unique_id}.srt"
    await file.download_to_drive(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    segments = re.split(r"(\n\d+\n\d{2}:\d{2}:\d{2},\d{3} --> .*?\n)", content)
    segments = [segments[i] + segments[i + 1] for i in range(1, len(segments), 2)]

    for lang_code in languages:
        translated_srt = ""
        for segment in segments:
            parts = segment.split("\n")
            if len(parts) < 3:
                continue
            text = " ".join(parts[2:]).strip()
            try:
                translated = GoogleTranslator(source='auto', target=lang_code).translate(text)
                new_segment = f"{parts[0]}\n{parts[1]}\n{text}\n{translated}\n\n"
                translated_srt += new_segment
            except Exception as e:
                translated_srt += f"{parts[0]}\n{parts[1]}\n{text}\n[Translation failed]\n\n"

        output_path = f"/tmp/translated_{lang_code}.srt"
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(translated_srt)

        await context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(output_path))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\u0421\u043a\u0430\u0441\u043e\u0432\u0430\u043d\u043e")
    return ConversationHandler.END

if __name__ == '__main__':
    from telegram.ext import ApplicationBuilder

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_language_selection)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Document.FILE_NAME.endswith(".srt"), handle_file))

    application.run_polling()
