import os
import re
import tempfile
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from deep_translator import GoogleTranslator

# Логування
logging.basicConfig(level=logging.INFO)

# Зберігання станів користувачів
user_states = {}

# Список мов
LANGUAGES = {
    "🇺🇸 English": "en",
    "🇺🇦 Ukrainian": "uk",
    "🇩🇪 German": "de",
    "🇫🇷 French": "fr",
    "🇪🇸 Spanish": "es",
    "🇮🇹 Italian": "it",
    "🇵🇱 Polish": "pl",
    "🇷🇴 Romanian": "ro",
    "🇹🇷 Turkish": "tr",
    "🇸🇦 Arabic": "ar",
    "🇨🇳 Chinese": "zh-CN",
    "🇯🇵 Japanese": "ja",
    "🇰🇷 Korean": "ko",
    "🇮🇳 Hindi": "hi",
    "🇧🇷 Portuguese": "pt"
}

# Команда старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Надішли .srt файл субтитрів для перекладу.")

# Отримання .srt файлу
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith(".srt"):
        await update.message.reply_text("❌ Надішли файл у форматі .srt.")
        return

    file = await document.get_file()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        user_states[update.effective_user.id] = {
            "file_path": tmp.name,
            "selected_languages": []
        }

    # Створення кнопок мов
    keyboard = [[InlineKeyboardButton(lang, callback_data=code)] for lang, code in LANGUAGES.items()]
    keyboard.append([InlineKeyboardButton("✅ Переклад", callback_data="translate")])

    await update.message.reply_text(
        "✅ Файл отримано. Обери мови перекладу:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Обробка кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_states:
        await query.edit_message_text("⛔ Спочатку надішли файл.")
        return

    state = user_states[user_id]

    if query.data == "translate":
        if not state["selected_languages"]:
            await query.edit_message_text("⚠️ Ви не обрали жодної мови.")
            return

        await query.edit_message_text(f"🔁 Починаю переклад на: {', '.join(state['selected_languages'])}...")
        await perform_translation(user_id, context)
    else:
        lang_code = query.data
        if lang_code not in state["selected_languages"]:
            state["selected_languages"].append(lang_code)

# Переклад .srt
async def perform_translation(user_id, context: ContextTypes.DEFAULT_TYPE):
    state = user_states[user_id]
    original_path = state["file_path"]

    with open(original_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    blocks = []
    block = []

    for line in lines:
        if line.strip() == "":
            if block:
                blocks.append(block)
                block = []
        else:
            block.append(line)
    if block:
        blocks.append(block)

    for lang_code in state["selected_languages"]:
        translated_blocks = []
        for block in blocks:
            translated_block = []
            for line in block:
                if re.match(r"^\d+$", line.strip()) or "-->" in line:
                    translated_block.append(line)
                elif line.strip():
                    translated = GoogleTranslator(source="auto", target=lang_code).translate(line.strip())
                    translated_block.append(translated + "\n")
                else:
                    translated_block.append("\n")
            translated_blocks.append(translated_block)

        translated_content = "\n".join(["".join(b) for b in translated_blocks])

        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{lang_code}.srt", mode="w", encoding="utf-8") as out_file:
            out_file.write(translated_content)
            output_path = out_file.name

        await context.bot.send_document(
            chat_id=user_id,
            document=InputFile(output_path),
            filename=f"translated_{lang_code}.srt"
        )

# Запуск через Webhook
if __name__ == "__main__":
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")

    if not TOKEN or not WEBHOOK_URL:
        raise ValueError("TELEGRAM_TOKEN і WEBHOOK_URL мають бути вказані як змінні середовища.")

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL
    )
