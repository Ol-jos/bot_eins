import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from deep_translator import GoogleTranslator

# ===== Налаштування =====
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

logging.basicConfig(level=logging.INFO)

# ===== Глобальні змінні =====
user_data = {}

LANGUAGES = {
    "uk": "Українська", "en": "Англійська", "fr": "Французька", "es": "Іспанська",
    "it": "Італійська", "pl": "Польська", "de": "Німецька", "pt": "Португальська",
    "nl": "Голландська", "ja": "Японська", "ko": "Корейська", "tr": "Турецька",
    "ru": "Російська", "ar": "Арабська", "zh-CN": "Китайська (спрощена)"
}


# ===== Обробники =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені файл субтитрів .srt для перекладу.")
    user_data[update.effective_user.id] = {
        "state": "WAITING_FOR_FILE",
        "selected_languages": [],
        "srt_lines": []
    }


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    file = update.message.document

    if not file.file_name.endswith(".srt"):
        await update.message.reply_text("Будь ласка, надішли файл з розширенням .srt.")
        return

    file_obj = await file.get_file()
    file_content = await file_obj.download_as_bytes()
    lines = file_content.decode("utf-8").splitlines()

    # Зберігаємо файл у пам'яті
    user_data[user_id]["srt_lines"] = lines
    user_data[user_id]["state"] = "CHOOSING_LANGUAGES"
    user_data[user_id]["selected_languages"] = []

    # Генеруємо кнопки мов
    buttons = [
        [InlineKeyboardButton(name, callback_data=code)]
        for code, name in LANGUAGES.items()
    ]
    buttons.append([InlineKeyboardButton("✅ Переклад", callback_data="translate")])

    await update.message.reply_text(
        "Файл отримано! Обери мови для перекладу й натисни 'Переклад':",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_data or user_data[user_id]["state"] != "CHOOSING_LANGUAGES":
        await query.edit_message_text("Будь ласка, спочатку надішли .srt файл.")
        return

    if data == "translate":
        langs = user_data[user_id]["selected_languages"]
        if not langs:
            await query.edit_message_text("Спочатку обери хоча б одну мову.")
            return

        await query.edit_message_text(f"Починаю переклад на мови: {', '.join(langs)}...")
        await perform_translation(user_id, context)
    else:
        if data in LANGUAGES and data not in user_data[user_id]["selected_languages"]:
            user_data[user_id]["selected_languages"].append(data)
            await query.answer(f"Додано: {LANGUAGES[data]}")
        else:
            await query.answer("Мова вже обрана або некоректна.")


async def perform_translation(user_id, context):
    lines = user_data[user_id]["srt_lines"]
    languages = user_data[user_id]["selected_languages"]

    text_lines = []
    for line in lines:
        if line.strip().isdigit() or "-->" in line or not line.strip():
            text_lines.append(line)
        else:
            text_lines.append(line.strip())

    for lang_code in languages:
        translated_lines = []
        for line in lines:
            if line.strip().isdigit() or "-->" in line or not line.strip():
                translated_lines.append(line)
            else:
                try:
                    translated = GoogleTranslator(source='auto', target=lang_code).translate(line)
                    translated_lines.append(translated)
                except Exception as e:
                    translated_lines.append(f"[Помилка перекладу: {e}]")

        content = "\n".join(translated_lines)
        with open(f"translated_{lang_code}.srt", "w", encoding="utf-8") as f:
            f.write(content)

        with open(f"translated_{lang_code}.srt", "rb") as f:
            await context.bot.send_document(
                chat_id=user_id,
                document=f,
                filename=f"translated_{lang_code}.srt",
                caption=LANGUAGES[lang_code]
            )

    user_data[user_id]["state"] = "DONE"


# ===== Webhook =====
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return 'ok', 200


# ===== Реєстрація обробників =====
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
application.add_handler(CallbackQueryHandler(handle_callback))


# ===== Запуск Flask із Webhook =====
if __name__ == "__main__":
    if not TOKEN or not WEBHOOK_URL:
        raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути задані в середовищі.")

    import asyncio
    asyncio.run(application.bot.set_webhook(url=WEBHOOK_URL))

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
