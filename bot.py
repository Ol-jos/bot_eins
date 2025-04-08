import os
import re
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from deep_translator import GoogleTranslator
from flask import Flask, request

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен з середовища
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Flask — для Render ping
app = Flask(__name__)
@app.route('/')
def index():
    return "Bot is running!"

# Мови для вибору
LANGUAGES = {
    "Arabic 🇵🇸": "arabic",
    "English 🇬🇧": "english",
    "Ukrainian 🇺🇦": "ukrainian",
    "French 🇫🇷": "french",
    "Spanish 🇪🇸": "spanish",
    "German 🇩🇪": "german",
    "Italian 🇮🇹": "italian",
    "Polish 🇵🇱": "polish",
    "Romanian 🇷🇴": "romanian",
    "Portuguese 🇵🇹": "portuguese",
    "Russian 🇷🇺": "russian",
    "Turkish 🇹🇷": "turkish",
    "Dutch 🇳🇱": "dutch",
    "Hebrew 🇮🇱": "hebrew",
    "Chinese 🇨🇳": "chinese (simplified)"
}

# Стан для вибору мови
LANGUAGE_SELECTION = 1

# Тимчасове сховище
user_data_store = {}

# Обробка /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[lang] for lang in LANGUAGES.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🌍 Обери мови для перекладу (до 15), потім натисни\n⏰ Почати переклад",
        reply_markup=reply_markup
    )
    user_data_store[update.effective_user.id] = {"languages": []}
    return LANGUAGE_SELECTION

# Обробка вибору мови
async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.message.text
    data = user_data_store.get(update.effective_user.id)
    if not data:
        await update.message.reply_text("🌍 Please choose your target language:")
        return LANGUAGE_SELECTION

    if lang == "⏰ Почати переклад":
        if not data["languages"]:
            await update.message.reply_text("❌ Спочатку вибери хоч одну мову.")
            return LANGUAGE_SELECTION
        await update.message.reply_text("⏳ Перекладаю...")
        return ConversationHandler.END

    if lang in LANGUAGES:
        if lang not in data["languages"] and len(data["languages"]) < 15:
            data["languages"].append(lang)
            await update.message.reply_text(f"✅ Додано: {lang}")
        else:
            await update.message.reply_text("⚠️ Вже додано або ліміт 15 мов.")
    else:
        await update.message.reply_text("❌ Неправильна мова. Обери з клавіатури.")
    return LANGUAGE_SELECTION

# Обробка .srt файлу
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("❌ Надішли файл у форматі .srt")
        return

    file = await context.bot.get_file(document.file_id)
    content = await file.download_as_bytearray()
    srt_text = content.decode("utf-8")

    user_id = update.effective_user.id
    data = user_data_store.get(user_id)
    if not data or not data["languages"]:
        await update.message.reply_text("🌍 Please select a language first using /start.")
        return

    translations = {}
    for lang in data["languages"]:
        target = LANGUAGES[lang]
        translated = translate_srt(srt_text, target)
        translations[target] = translated

        # Відправити окремий файл
        await update.message.reply_document(
            document=translated.encode("utf-8"),
            filename=f"translated_{target}.srt"
        )

# Переклад одного .srt
def translate_srt(content: str, target_lang: str) -> str:
    entries = parse_srt(content)
    for entry in entries:
        entry["text"] = translate_text(entry["text"], target_lang)
    return build_srt(entries)

def translate_text(text: str, target_lang: str) -> str:
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return text

def parse_srt(content: str):
    blocks = re.split(r"\n\s*\n", content.strip())
    parsed = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) >= 3:
            parsed.append({
                "index": lines[0],
                "timing": lines[1],
                "text": " ".join(lines[2:])
            })
    return parsed

def build_srt(entries):
    return "\n\n".join(
        f"{e['index']}\n{e['timing']}\n{e['text']}" for e in entries
    )

# Основна логіка
if __name__ == "__main__":
    from threading import Thread
    Thread(target=app.run).start()

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={LANGUAGE_SELECTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), select_language)]},
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    application.run_polling()
