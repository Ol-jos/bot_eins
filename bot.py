import os
import re
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackContext
from deep_translator import GoogleTranslator
from flask import Flask

LANGUAGE_SELECTION, CONFIRM_TRANSLATION = range(2)
LANGUAGES = {
    "Arabic 🇸🇮": "arabic",
    "Chinese 🇨🇳": "chinese (simplified)",
    "English 🇬🇧": "english",
    "French 🇫🇷": "french",
    "German 🇩🇪": "german",
    "Hindi 🇥🇰": "hindi",
    "Italian 🇮🇹": "italian",
    "Japanese 🇯🇵": "japanese",
    "Korean 🇰🇷": "korean",
    "Polish 🇵🇱": "polish",
    "Portuguese 🇵🇹": "portuguese",
    "Russian 🇷🇺": "russian",
    "Spanish 🇪🇸": "spanish",
    "Turkish 🇹🇷": "turkish",
    "Ukrainian 🇺🇦": "ukrainian"
}
LANGUAGE_BUTTONS = [
    [KeyboardButton(text)] for text in LANGUAGES.keys()
] + [["🚀 Почати переклад"]]

user_data_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("📂 Надішли файл субтитрів у форматі .srt для початку.")
    return LANGUAGE_SELECTION

def parse_srt(srt_content):
    entries = []
    blocks = re.split(r'\n\n', srt_content.strip())
    for block in blocks:
        lines = block.strip().split('\n')
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

def translate_text(text: str, target_lang: str) -> str:
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except:
        return text

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("❌ Це не файл субтитрів .srt. Спробуй ще раз.")
        return LANGUAGE_SELECTION

    file = await document.get_file()
    srt_path = f"temp_{update.effective_user.id}.srt"
    await file.download_to_drive(srt_path)

    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    entries = parse_srt(srt_content)
    os.remove(srt_path)

    user_data_store[update.effective_user.id] = {
        "entries": entries,
        "languages": []
    }

    await update.message.reply_text(
        "🌍 Обери мови для перекладу (до 15), потім натисни \"\ud83d\ude80 Почати переклад\"",
        reply_markup=ReplyKeyboardMarkup(LANGUAGE_BUTTONS, resize_keyboard=True)
    )
    return CONFIRM_TRANSLATION

async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "🚀 Почати переклад":
        return await start_translation(update, context)

    if text not in LANGUAGES:
        return await update.message.reply_text("❌ Невідома мова. Обери з клавіатури.")

    lang_code = LANGUAGES[text]
    data = user_data_store.get(user_id, {})
    if lang_code not in data.get("languages", []):
        data["languages"].append(lang_code)
        user_data_store[user_id] = data
        await update.message.reply_text(f"✅ Додано: {text}")
    else:
        await update.message.reply_text(f"⚠️ Мову {text} вже додано.")
    return CONFIRM_TRANSLATION

async def start_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data_store.get(user_id)
    if not data or not data.get("entries"):
        await update.message.reply_text("❗ Спочатку надішли файл субтитрів.")
        return LANGUAGE_SELECTION

    langs = data.get("languages", [])
    if not langs:
        await update.message.reply_text("❗ Не обрано жодної мови.")
        return CONFIRM_TRANSLATION

    await update.message.reply_text(
        f"⏳ Починаю переклад на: {', '.join(langs)}",
        reply_markup=ReplyKeyboardRemove()
    )

    for lang in langs:
        translated_entries = []
        for entry in data["entries"]:
            translated_text = translate_text(entry["text"], lang)
            translated_entries.append({
                "index": entry["index"],
                "timing": entry["timing"],
                "text": translated_text
            })
        srt_output = build_srt(translated_entries)
        path = f"translated_{lang}.srt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(srt_output)
        await update.message.reply_document(InputFile(path))
        os.remove(path)

    return ConversationHandler.END

if __name__ == '__main__':
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE_SELECTION: [MessageHandler(filters.Document.ALL, handle_file)],
            CONFIRM_TRANSLATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_language)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    application.add_handler(conv_handler)
    application.run_polling()
