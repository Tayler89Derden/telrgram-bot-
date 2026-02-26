import os
import logging
import asyncio
import smtplib
from email.mime.text import MIMEText

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Логирование — видно в Render Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Обязательные переменные из Render Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в Environment Variables Render!")

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Используй App Password от Google!

# Порт от Render (обычно 10000 на free tier)
PORT = int(os.getenv("PORT", "10000"))

async def send_email(subject: str, body: str) -> None:
    if not all([EMAIL_SENDER, EMAIL_RECEIVER, EMAIL_PASSWORD]):
        logger.warning("Email переменные не заданы — пропускаем отправку")
        return

    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email отправлен: {subject}")
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")


# Пример: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я бот на Render с webhook.\n"
        "Напиши сообщение — я повторю + отправлю email (если настроено)."
    )


# Пример: эхо + email при сообщении
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user = update.effective_user
    reply = f"Ты написал: {text}\n(от {user.username or user.full_name})"

    await update.message.reply_text(reply)

    # Отправляем email (раскомментируй или измени условие)
    # await send_email(
    #     "Новое сообщение в боте",
    #     f"Пользователь: {user.username or user.id}\nТекст: {text}"
    # )


async def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    # ← Добавь здесь ВСЕ свои хендлеры
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Можно добавить job_queue, другие handlers, persistence и т.д.

    # Хост от Render (автоматически: твой-сервис.onrender.com)
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not host:
        raise RuntimeError("RENDER_EXTERNAL_HOSTNAME не найден — запуск только на Render!")

    webhook_url = f"https://{host}/{BOT_TOKEN}"
    url_path = BOT_TOKEN  # Безопасно: путь = токен

    logger.info(f"Запуск webhook на: {webhook_url} (порт {PORT})")

    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=url_path,
        webhook_url=webhook_url,
        drop_pending_updates=True,          # Очищает старые обновления при рестарте
        allowed_updates=Update.ALL_TYPES,   # Или укажи только нужные: ["message"]
        bootstrap_retries=5,                # Пытается 5 раз при сетевых проблемах
        # secret_token="мой_секрет",        # Опционально: для защиты от фейковых запросов
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен нормально")
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}", exc_info=True)
        raise
