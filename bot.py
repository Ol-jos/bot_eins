import os
import re
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, filters,
                          ContextTypes, CallbackQueryHandler, ConversationHandler)
from deep_translator import GoogleTranslator
from flask import Flask, request

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# States
WAITING_FOR_FILE, LANGUAGE_SELECTION = range(2)

# Available languages (code: name + emoji)
LANGUAGES = {
    "en": "English 🇬🇧",
    "uk": "Ukrainian 🇺🇦",
    "ar": "Arabic 🇦🇪",
    "fr": "French 🇫🇷",
    "es": "Spanish 🇪🇸",
    "it": "Italian 🇮🇹",
    "de": "German 🇩🇪",
    "pl": "Polish 🇵🇱",
    "ro": "Romanian 🇷🇴",
    "pt": "Portuguese 🇵🇹",
    "zh-CN": "Chinese 🇨🇳",
    "ja": "Japanese 🇯🇵",
    "ko": "Korean 🇰🇷",
    "tr": "Turkish 🇹🇷",
    "cs": "Czech 🇨🇿"
}

user_data_store = {}

# Handle /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_store[update.effective_user.id] = {"languages": []}
    await update.message.reply_text(
        "📢 Надішли мені .srt файл для перекладу."
    )
    return WAITING_FOR_FILE

# Handle file upload
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("❌ Надішли файл у форматі .srt")
        return WAITING_FOR_FILE

    file = await context.bot.get_file(document.file_id)
    srt_content = (await file.download_as_bytearray()).decode("utf-8")
    user_data_store[update.effective_user.id]["srt"] = srt_content

    keyboard = [
        [InlineKeyboardButton(name, callback_data=code)]
        for code, name in LANGUAGES.items()
    ] + [[InlineKeyboardButton("⏰ Почати переклад", callback_data="translate")]]

    await update.message.reply_text(
        "🌍 Обери мови для перекладу (до 15), потім натисни \u23f0 Почати переклад",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return LANGUAGE_SELECTION

# Handle language selection buttons
async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "translate":
        languages = user_data_store[user_id].get("languages", [])
        if not languages:
            await query.edit_message_text("❌ Ти не обрав жодної мови.")
            return LANGUAGE_SELECTION

        await query.edit_message_text(
            f"⌛ Перекладаю на: {', '.join([LANGUAGES[code] for code in languages])}"
        )

        original_srt = user_data_store[user_id]["srt"]
        for lang_code in languages:
            translated = await translate_srt(original_srt, lang_code)
            with open(f"translated_{lang_code}.srt", "w", encoding="utf-8") as f:
                f.write(translated)
            await context.bot.send_document(
                chat_id=user_id,
                document=open(f"translated_{lang_code}.srt", "rb"),
                filename=f"translated_{lang_code}.srt"
            )
        return ConversationHandler.END

    if data in LANGUAGES:
        selected = user_data_store[user_id].setdefault("languages", [])
        if data not in selected:
            selected.append(data)
            await query.answer(f"✅ Додано: {LANGUAGES[data]}")
        else:
            await query.answer("⚠️ Вже додано.")
    return LANGUAGE_SELECTION

# Переклад субтитрів
async def translate_srt(srt_content, target_lang):
    try:
        blocks = re.split(r"\n\n", srt_content)
        translated_blocks = []
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                idx, timing, *text = lines
                translated_text = GoogleTranslator(source="auto", target=target_lang).translate(" ".join(text))
                translated_blocks.append(f"{idx}\n{timing}\n{translated_text}")
        return "\n\n".join(translated_blocks)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return srt_content

# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# Run Telegram bot
if __name__ == '__main__':
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not TOKEN or not WEBHOOK_URL:
        raise Exception("Missing TELEGRAM_TOKEN or WEBHOOK_URL environment variable")

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, handle_file)],
            LANGUAGE_SELECTION: [CallbackQueryHandler(handle_language_selection)]
        },
        fallbacks=[]
    )
    application.add_handler(conv_handler)

    # Set webhook
    async def run():
        await application.bot.set_webhook(WEBHOOK_URL)
        await application.initialize()
        await application.start()
        await application.updater.start_polling()

    import asyncio
    asyncio.run(run())

    # Flask run (for webhook entry)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    if __name__ == "__main__":
    import os

    TOKEN = os.getenv("TELEGRAM_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")

    if not TOKEN or not WEBHOOK_URL:
        raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути задані як змінні середовища.")

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL,
    )
