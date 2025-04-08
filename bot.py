import os
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from deep_translator import GoogleTranslator
import re
from flask import Flask, request

# Завантаження токена з середовища
TOKEN = os.environ.get("TELEGRAM_TOKEN")

LANGUAGE_SELECTION = range(1)
user_data_store = {}

# --- Основні мови ---
LANGUAGES = {
    "Arabic 🇦🇪": "ar",
    "English 🇬🇧": "en",
    "Ukrainian 🇺🇦": "uk",
    "French 🇫🇷": "fr",
    "Spanish 🇪🇸": "es",
    "German 🇩🇪": "de",
    "Polish 🇵🇱": "pl",
    "Russian 🇷🇺": "ru",
    "Italian 🇮🇹": "it",
    "Portuguese 🇵🇹": "pt",
    "Dutch 🇳🇱": "nl",
    "Turkish 🇹🇷": "tr",
    "Japanese 🇯🇵": "ja",
    "Korean 🇰🇷": "ko",
    "Chinese 🇨🇳": "zh-CN",
}

language_buttons = [[KeyboardButton(text)] for text in LANGUAGES.keys()]

def translate_line(line, target_lang):
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(line)
    except Exception as e:
        print(f"Translation error: {e}")
        return line

def format_subtitle_block(block_num, time_range, original, translated):
    return f"{block_num}\n{time_range}\n{original}\n{translated}\n"

def parse_srt(srt_text):
    blocks = srt_text.strip().split("\n\n")
    parsed = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            block_num = lines[0]
            time_range = lines[1]
            text = "\n".join(lines[2:])
            parsed.append((block_num, time_range, text))
    return parsed

def write_srt(parsed_blocks, translations):
    output = ""
    for (block_num, time_range, original), translated in zip(parsed_blocks, translations):
        output += format_subtitle_block(block_num, time_range, original, translated) + "\n"
    return output

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 Please choose your target language:",
        reply_markup=ReplyKeyboardMarkup(language_buttons, one_time_keyboard=True, resize_keyboard=True)
    )
    return LANGUAGE_SELECTION

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_lang = update.message.text
    user_id = update.message.from_user.id
    if user_lang in LANGUAGES:
        user_data_store[user_id] = LANGUAGES[user_lang]
        await update.message.reply_text("✅ Language selected! Now send me the .srt file.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Invalid language. Please choose from the keyboard.")
        return LANGUAGE_SELECTION

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lang = user_data_store.get(user_id)

    if not lang:
        await update.message.reply_text("⚠️ Please select a language first using /start.")
        return

    document = update.message.document
    if not document.file_name.lower().endswith(".srt"):
        await update.message.reply_text("⚠️ Please send a valid .srt file.")
        return

    file = await context.bot.get_file(document.file_id)
    file_path = f"temp_{document.file_unique_id}.srt"
    await file.download_to_drive(file_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            srt_text = f.read()

        parsed_blocks = parse_srt(srt_text)
        original_texts = [text for _, _, text in parsed_blocks]
        translated_texts = [translate_line(text, lang) for text in original_texts]

        output_srt = write_srt(parsed_blocks, translated_texts)
        output_file_path = f"translated_{document.file_unique_id}.srt"
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(output_srt)

        await update.message.reply_document(document=InputFile(output_file_path), filename="translated.srt")

    except Exception as e:
        print(f"Processing error: {e}")
        await update.message.reply_text("❌ Something went wrong during translation.")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(output_file_path):
            os.remove(output_file_path)

# --- Flask для Render ping ---
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is alive!"

# --- Telegram app ---
if __name__ == "__main__":
    print("🧪 ЦЕ ТОЧНО НОВА ВЕРСІЯ БОТА!")

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={LANGUAGE_SELECTION: [MessageHandler(filters.TEXT, set_language)]},
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Бот запущено. Надішли команду /start у Telegram")
    application.run_polling()
