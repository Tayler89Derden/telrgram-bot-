import os
import logging
import asyncio
import smtplib
from email.mime.text import MIMEText

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Настройка логирования (видно в консоли / логах Render)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные из Environment Variables в Render (добавь их там!)
BOT_TOKEN = os.getenv("BOT_TOKEN")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден в переменных окружения!")
    raise ValueError("BOT_TOKEN обязателен")

# Порт от Render (по умолчанию 10000, если не задан)
PORT = int(os.getenv("PORT", "10000"))

# Функция отправки email (оставил почти как было, добавил async и логи)
async def send_email(subject: str, body: str) -> None:
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info("Email успешно отправлен")
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")


# Пример хендлера /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! Я твой бот на Render с webhook.\nНапиши что-нибудь — я повторю.")


# Пример эхо-хендлера (для всех текстовых сообщений)
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    await update.message.reply_text(f"Ты написал: {text}")
    
    # Пример: отправляем email при каждом сообщении (убери или измени условие)
    # await send_email("Новое сообщение от бота", f"Пользователь: {update.effective_user.username}\nТекст: {text}")


async def main() -> None:
    # Строим приложение
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # Добавляем твои хендлеры здесь
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Здесь добавь остальные свои хендлеры, job_queue и т.д.

    # Получаем hostname от Render[](https://твой-сервис.onrender.com)
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not host:
        logger.error("RENDER_EXTERNAL_HOSTNAME не найден — это критично!")
        raise ValueError("Запускай только на Render или укажи WEBHOOK_HOST вручную")

    webhook_url = f"https://{host}/{BOT_TOKEN}"   # путь = токен (самый безопасный вариант)
    url_path = BOT_TOKEN

    logger.info(f"Устанавливаем webhook: {webhook_url}")

    # Запускаем webhook-сервер (самый простой способ)
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=url_path,
        webhook_url=webhook_url,
        drop_pending_updates=True,          # очищаем очередь старых обновлений
        allowed_updates=Update.ALL_TYPES,   # или укажи только нужные: ["message", "callback_query"]
        # secret_token="твой_секретный_токен",  # опционально, для защиты
    )

    # run_webhook блокирует выполнение, поэтому код ниже не нужен обычно
    # Но если хочешь что-то делать после запуска — используй job_queue или отдельные задачи


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
