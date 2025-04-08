import os
import re
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from deep_translator import GoogleTranslator
from telegram.constants import DocumentMimeType

TOKEN = os.environ.get("TELEGRAM_TOKEN")
LANGUAGE_SELECTION = range(1)
user_data_store = {}

LANGUAGES = {
    "Arabic 🇦🇪": "ar",
    "Chinese 🇨🇳": "zh-CN",
    "Czech 🇨🇿": "cs",
    "Dutch 🇳🇱": "nl",
    "English 🇬🇧": "en",
    "French 🇫🇷": "fr",
    "German 🇩🇪": "de",
    "Hindi 🇮🇳": "hi",
    "Indonesian 🇮🇩": "id",
    "Italian 🇮🇹": "it",
    "Japanese 🇯🇵": "ja",
    "Korean 🇰🇷": "ko",
    "Polish 🇵🇱": "pl",
    "Portuguese 🇵🇹": "pt",
    "Russian 🇷🇺": "ru",
    "Spanish 🇪🇸": "es",
    "Turkish 🇹🇷": "tr",
    "Ukrainian 🇺🇦": "uk"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(lang)] for lang in LANGUAGES.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("🌍 Обери мову, на яку потрібно перекласти файл:", reply_markup=reply_markup)
    return LANGUAGE_SELECTION

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = update.message.text
    if language not in LANGUAGES:
        await update.message.reply_text("❌ Будь ласка, обери мову з клавіатури")
        return LANGUAGE_SELECTION
    user_data_store[update.effective_user.id] = LANGUAGES[language]
    await update.message.reply_text("📄 Тепер надішли файл із субтитрами у форматі .srt")
    return ConversationHandler.END

def translate_text(text: str, target_lang: str) -> str:
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception:
        return text  # якщо щось піде не так — повернути оригінал

def parse_srt(srt_content):
    entries = []
    blocks = re.split(r'\n{2,}', srt_content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            index = lines[0]
            timing = lines[1]
            text = " ".join(lines[2:])
            entries.append({"index": index, "timing": timing, "text": text})
    return entries

def build_srt(entries):
    result = ""
    for entry in entries:
        result += f"{entry['index']}\n{entry['timing']}\n{entry['text']}\n\n"
    return result.strip()

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("❌ Надішли файл у форматі .srt")
        return

    file = await context.bot.get_file(document.file_id)
    file_path = f"temp_{document.file_unique_id}.srt"
    await file.download_to_drive(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    entries = parse_srt(srt_content)
    user_lang = user_data_store.get(update.effective_user.id, "en")

    for entry in entries:
        entry["text"] = translate_text(entry["text"], user_lang)

    translated_content = build_srt(entries)
    translated_path = f"translated_{user_lang}.srt"
    with open(translated_path, "w", encoding="utf-8") as f:
        f.write(translated_content)

    await update.message.reply_document(InputFile(translated_path))

application = ApplicationBuilder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        LANGUAGE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_language)]
    },
    fallbacks=[]
)

application.add_handler(conv_handler)
application.add_handler(MessageHandler(filters.Document.MIME_TYPE(DocumentMimeType.SUBRIP), handle_file))

if __name__ == '__main__':
    print("🧪 ЦЕ ТОЧНО НОВА ВЕРСІЯ БОТА!")
    application.run_polling()
    print("🤖 Бот запущено. Надішли команду /start у Telegram")
