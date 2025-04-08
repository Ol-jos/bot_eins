import os
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, ConversationHandler)
from deep_translator import GoogleTranslator
import re

TOKEN = "7731637662:AAH-GOMWgIJTo4hJkkte0_RJ6Al-Q4wvHuU"
LANGUAGE_SELECTION = range(1)
user_data_store = {}

# --- Основні мови ---
LANGUAGES = {
    "Arabic 🇦🇪": "ar",
    "English 🇬🇮7": "en",
    "Ukrainian 🇺🇶": "uk",
    "French 🇫🇷": "fr",
    "Spanish 🇪🇸": "es",
    "German 🇩🇪": "de",
    "Italian 🇮🇹": "it",
    "Russian 🇷🇺": "ru",
    "Polish 🇵🇱": "pl",
    "Turkish 🇹🇷": "tr",
    "Hindi 🇮🇳": "hi",
    "Portuguese 🇵🇩": "pt",
    "Japanese 🇯🇵": "ja",
    "Korean 🇰🇷": "ko",
    "Chinese 🇨🇳": "zh-CN"
}

# --- Розбір і побудова SRT ---
def parse_srt(content):
    blocks = content.strip().split("\n\n")
    entries = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            index = lines[0]
            timing = lines[1]
            text = lines[2:]
            entries.append({"index": index, "timing": timing, "text": text})
    return entries

def build_srt(entries):
    result = ""
    for entry in entries:
        result += f"{entry['index']}\n"
        result += f"{entry['timing']}\n"
        result += "\n".join(entry['text']) + "\n\n"
    return result.strip()

# --- Команди ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data_store[chat_id] = {"languages": [], "file": None}
    await update.message.reply_text(
        "📢 Вітаю! Надішли мені .srt файл, а потім обери мови для перекладу."
    )
    return LANGUAGE_SELECTION

async def handle_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    document = update.message.document

    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("⚠️ Надішли, будь ласка, файл у форматі .srt.")
        return

    file = await document.get_file()
    file_path = f"temp_{document.file_unique_id}.srt"
    await file.download_to_drive(file_path)

    user_data_store[chat_id] = {"languages": [], "file": file_path}

    keyboard = [[KeyboardButton(lang)] for lang in LANGUAGES.keys()]
    keyboard.append([KeyboardButton("⏰ Почати переклад")])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)

    await update.message.reply_text(
        "🌍 Обери мови для перекладу (до 15), потім натисни ⏰ Почати переклад",
        reply_markup=reply_markup
    )
    return LANGUAGE_SELECTION

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    selected = update.message.text

    if selected == "⏰ Почати переклад":
        await start_translation(update, context)
        return ConversationHandler.END

    if selected in LANGUAGES and LANGUAGES[selected] not in user_data_store[chat_id]["languages"]:
        if len(user_data_store[chat_id]["languages"]) < 15:
            user_data_store[chat_id]["languages"].append(LANGUAGES[selected])
            await update.message.reply_text(f"✅ Додано: {selected}")
    return LANGUAGE_SELECTION

async def start_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = user_data_store.get(chat_id)
    if not data or not data["file"]:
        await update.message.reply_text("⚠️ Спочатку надішли файл .srt")
        return

    await update.message.reply_text("⏳ Перекладаю...")

    with open(data["file"], "r", encoding="utf-8") as f:
        srt_text = f.read()
    parsed = parse_srt(srt_text)

    if not parsed:
        await update.message.reply_text("❌ Не вдалося розпізнати субтитри у файлі.")
        return

    print(f"📄 Файл містить {len(parsed)} субтитрів. Переклад на: {data['languages']}\n")

    for lang_code in data["languages"]:
        translated = []
        print(f"🔄 Переклад на {lang_code}...")
        for entry in parsed:
            try:
                original_text = " ".join(entry["text"])
                translated_text = GoogleTranslator(source='auto', target=lang_code).translate(original_text)
                translated.append({
                    "index": entry["index"],
                    "timing": entry["timing"],
                    "text": [translated_text or "[Empty translation]"]
                })
            except Exception as e:
                print(f"❌ Помилка при перекладі ({lang_code}): {e}")

        result_text = build_srt(translated)
        print("🧾 Перевірка build_srt():")
        print(result_text[:500])

        result_path = f"translated_{lang_code}.srt"

        try:
            with open(result_path, "w", encoding="utf-8") as file:
                file.write(result_text)
            print("✅ Файл збережено:", result_path)
            with open(result_path, "rb") as file_to_send:
                await update.message.reply_document(document=InputFile(file_to_send, filename=result_path))
        except Exception as e:
            print(f"❌ Помилка запису файлу {result_path}: {e}")

        if os.path.exists(result_path):
            os.remove(result_path)
            print(f"🗑️ Видалено тимчасовий файл: {result_path}")

    os.remove(data["file"])
    user_data_store.pop(chat_id, None)
    await update.message.reply_text("✅ Готово! Надішли новий файл, якщо хочеш ще раз перекласти.")

# --- Запуск ---
app = ApplicationBuilder().token(TOKEN).build()
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        LANGUAGE_SELECTION: [
            MessageHandler(filters.Document.ALL, handle_srt_file),
            MessageHandler(filters.TEXT & ~filters.COMMAND, select_language)
        ]
    },
    fallbacks=[]
)

app.add_handler(conv_handler)
print("🧪 ЦЕ ТОЧНО НОВА ВЕРСІЯ БОТА!")
print("🤖 Бот запущено. Надішли команду /start у Telegram")
app.run_polling()
