import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from deep_translator import GoogleTranslator

app = Flask(__name__)
application = None

# Стан користувача
user_states = {}

# Доступні мови перекладу
LANGUAGES = {
    "en": "Англійська",
    "uk": "Українська",
    "de": "Німецька",
    "fr": "Французька",
    "it": "Італійська",
    "es": "Іспанська",
    "ru": "Російська",
    "zh-CN": "Китайська",
    "ja": "Японська",
    "ko": "Корейська",
    "pt": "Португальська",
    "pl": "Польська",
    "nl": "Нідерландська",
    "tr": "Турецька",
    "ar": "Арабська",
}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені .srt файл для перекладу.")

# Обробка документа
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("Будь ласка, надішли .srt файл.")
        return

    file = await context.bot.get_file(document.file_id)
    content = await file.download_as_bytearray()
    user_states[update.effective_user.id] = {
        "content": content.decode("utf-8"),
        "languages": set()
    }

    keyboard = [[InlineKeyboardButton(name, callback_data=code)] for code, name in LANGUAGES.items()]
    keyboard.append([InlineKeyboardButton("✅ Переклад", callback_data="translate")])

    await update.message.reply_text(
        "Оберіть мови для перекладу, потім натисніть \"Переклад\":",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Обробка вибору мови або кнопки "Переклад"
async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_states:
        await query.edit_message_text("Спершу надішліть .srt файл!")
        return

    if data == "translate":
        await query.edit_message_text("Починаю переклад на: " + ", ".join(
            LANGUAGES[code] for code in user_states[user_id]["languages"]
        ))

        original_lines = user_states[user_id]["content"].splitlines()

        for lang_code in user_states[user_id]["languages"]:
            translated_lines = []
            for line in original_lines:
                if line.strip().isdigit() or "-->") in line or not line.strip():
                    translated_lines.append(line)
                else:
                    try:
                        translated = GoogleTranslator(source="auto", target=lang_code).translate(line)
                        translated_lines.append(translated)
                    except Exception:
                        translated_lines.append(line + " (помилка перекладу)")

            result = "\n".join(translated_lines)
            file_name = f"translation_{lang_code}.srt"
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(result)

            await context.bot.send_document(chat_id=user_id, document=open(file_name, "rb"))
        return

    state = user_states[user_id]
    if data in state["languages"]:
        state["languages"].remove(data)
    else:
        state["languages"].add(data)

# === Flask Webhook ===
@app.route("/webhook", methods=["POST"])
async def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return "ok"
    return "method not allowed", 405

# === Async main ===
async def run():
    global application
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN не задано")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(CallbackQueryHandler(handle_language_choice))

    await application.initialize()
    await application.start()
    print("✅ Bot initialized and webhook set")

if __name__ == "__main__":
    asyncio.run(run())
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
