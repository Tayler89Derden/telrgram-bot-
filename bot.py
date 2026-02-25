import os
import logging
import smtplib
from email.mime.text import MIMEText
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext

# Настройка логирования (чтобы видеть ошибки в консоли/логах Render)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные окружения (из скриншота, но без пробелов в пароле)
# В Render добавь их в Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8266619758:AAFcWOk4ybVNC_-TZU1QcCxFPCfjMqD26I')
EMAIL_SENDER = os.environ.get('EMAIL_SENDER', 'lastudioonline@gmail.com')
EMAIL_RECEIVER = os.environ.get('EMAIL_RECEIVER', 'lastudioonline@gmail.com')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', 'qfowkjvpehjenlip')  # Без пробелов!

# Порт для webhook (Render назначит PORT автоматически)
PORT = int(os.environ.get('PORT', 8443))

# Функция отправки email с полной отладкой
async def send_email(subject: str, body: str):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER

        # Подключение к Gmail (порт 587 + STARTTLS — самый надёжный)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Шифрование
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        logger.info("Email успешно отправлен!")
        return True

    except Exception as e:
        logger.error(f"Ошибка при отправке email: {str(e)}")
        return False

# Пример обработчика /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Это бот с анкетой. Напиши что-нибудь, и я отправлю на email.")

# Пример обработчика сообщений (здесь логика анкеты — адаптируй под свою)
async def handle_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    logger.info(f"Получено сообщение: {user_message}")

    # Здесь твоя логика анкеты (сбор данных)
    # Предположим, что после анкеты отправляем email
    subject = "Новое сообщение от бота"
    body = f"Пользователь {update.message.from_user.username} написал: {user_message}"

    if await send_email(subject, body):
        await update.message.reply_text("Сообщение отправлено на email!")
    else:
        await update.message.reply_text("Ошибка отправки email. Проверь логи.")

# Обработчик ошибок (чтобы бот не падал молча)
async def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Ошибка: {context.error}")

def main():
    print("[START] BOT_TOKEN найден, длина:", len(BOT_TOKEN))
    print("[START] Запуск бота...")

    # Создание приложения (python-telegram-bot v21+)
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Запуск с webhook (чтобы избежать конфликтов getUpdates на Render)
    # Render даёт https://{project-name}.onrender.com бесплатно
    webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/{BOT_TOKEN}"
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=webhook_url
    )

if __name__ == '__main__':
    main()
