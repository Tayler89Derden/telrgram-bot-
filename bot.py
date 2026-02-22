import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ConversationHandler, ContextTypes, filters
)

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Удалили PERSONALITY, теперь состояний 19
FIO, DOB, CITY, CONTACT, EMAIL, DOC, HEIGHT, WEIGHT, CLOTHES, BREAST, \
HAIR, EYES, TATTOO, PHOTOS, EXPERIENCE, HOURS, DAYS, TIME, LIMITS = range(19)

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Важно: smtp.gmail.com и порт 465
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        return True
    except Exception as e:
        print(f"!!! ОШИБКА SMTP: {e}") # Это появится в логах Render
        return False

# ... (Функции до days_step остаются такими же)

async def days_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Дни"] = update.message.text
    kb = [["Утро", "День", "Вечер", "Ночь"]]
    await update.message.reply_text("Предпочтительное время:", 
                                   reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return TIME

async def time_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Время"] = update.message.text
    # ПРЫГАЕМ СРАЗУ НА LIMITS, пропуская Личные качества
    await update.message.reply_text("Что допустимо в работе?", reply_markup=ReplyKeyboardRemove())
    return LIMITS

async def limits_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Допустимое"] = update.message.text
    
    summary = "📋 НОВАЯ АНКЕТА\n" + "="*20 + "\n"
    for key, value in context.user_data.items():
        if key != "Фото":
            summary += f"🔹 {key}: {value}\n"

    await update.message.reply_text("Отправляю анкету...")
    
    if send_email(f"Анкета: {context.user_data.get('ФИО')}", summary):
        await update.message.reply_text("✅ Анкета доставлена!")
    else:
        await update.message.reply_text("⚠️ Ошибка почты. Проверьте настройки SMTP.")
    
    return ConversationHandler.END

# --- ВАЖНО: Обнови ConversationHandler в main() ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fio_step)],
            DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, dob_step)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city_step)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_step)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_step)],
            DOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, doc_step)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, height_step)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight_step)],
            CLOTHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, clothes_step)],
            BREAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, breast_step)],
            HAIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, hair_step)],
            EYES: [MessageHandler(filters.TEXT & ~filters.COMMAND, eyes_step)],
            TATTOO: [MessageHandler(filters.TEXT & ~filters.COMMAND, tattoo_step)],
            PHOTOS: [MessageHandler(filters.PHOTO, photos_step)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, experience_step)],
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, hours_step)],
            DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, days_step)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time_step)],
            LIMITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, limits_step)], # Убрали PERSONALITY здесь
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    app.run_polling()
