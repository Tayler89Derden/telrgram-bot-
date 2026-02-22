import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# --- НАСТРОЙКИ (берутся из Render Environment) ---
TOKEN = os.getenv("BOT_TOKEN")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Состояния анкеты (20 этапов)
(
    FIO, DOB, CITY, CONTACT, EMAIL, DOC,
    HEIGHT, WEIGHT, CLOTHES, BREAST, HAIR, EYES, TATTOO, PHOTOS,
    EXPERIENCE, HOURS, DAYS, TIME, PERSONALITY, LIMITS
) = range(20)

# --- ФУНКЦИЯ ОТПРАВКИ ПОЧТЫ ---
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Для Gmail/Mail.ru/Yandex используем SSL порт 465
        # Если используешь Gmail, хост: smtp.gmail.com
        # Если Mail.ru, хост: smtp.mail.ru
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        return True
    except Exception as e:
        print(f"Ошибка SMTP: {e}")
        return False

# --- ОБРАБОТЧИКИ АНКЕТЫ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Здравствуйте! Введите Ваше ФИО:")
    return FIO

async def fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ФИО"] = update.message.text
    await update.message.reply_text("Дата рождения (18+):")
    return DOB

async def dob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Дата рождения"] = update.message.text
    await update.message.reply_text("Город проживания:")
    return CITY

async def city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Город"] = update.message.text
    await update.message.reply_text("Контакт (Тел/ТГ):")
    return CONTACT

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Контакт"] = update.message.text
    await update.message.reply_text("Ваш Email:")
    return EMAIL

async def email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Email"] = update.message.text
    kb = [["Да", "Нет"]]
    await update.message.reply_text("Документ подтверждающий возраст есть?", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return DOC

async def doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Документ"] = update.message.text
    await update.message.reply_text("Рост:", reply_markup=ReplyKeyboardRemove())
    return HEIGHT

async def height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Рост"] = update.message.text
    await update.message.reply_text("Вес:")
    return WEIGHT

async def weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Вес"] = update.message.text
    await update.message.reply_text("Размер одежды:")
    return CLOTHES

async def clothes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Размер одежды"] = update.message.text
    await update.message.reply_text("Размер груди:")
    return BREAST

async def breast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Размер груди"] = update.message.text
    await update.message.reply_text("Цвет волос:")
    return HAIR

async def hair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Цвет волос"] = update.message.text
    await update.message.reply_text("Цвет глаз:")
    return EYES

async def eyes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Цвет глаз"] = update.message.text
    await update.message.reply_text("Тату/пирсинг:")
    return TATTOO

async def tattoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Тату"] = update.message.text
    context.user_data["Фото"] = []
    await update.message.reply_text("Пришлите 3 фото (по одному).")
    return PHOTOS

async def photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["Фото"].append(update.message.photo[-1].file_id)
    
    count = len(context.user_data["Фото"])
    if count < 3:
        await update.message.reply_text(f"Получено {count}/3. Жду еще.")
        return PHOTOS
    
    await update.message.reply_text("Опыт работы:")
    return EXPERIENCE

async def experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Опыт"] = update.message.text
    await update.message.reply_text("Часов в день?")
    return HOURS

async def hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Часы"] = update.message.text
    await update.message.reply_text("Дней в неделю?")
    return DAYS

async def days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Дни"] = update.message.text
    kb = [["Утро", "День", "Вечер", "Ночь"]]
    await update.message.reply_text("Время:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return TIME

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Время"] = update.message.text
    await update.message.reply_text("Личные качества:", reply_markup=ReplyKeyboardRemove())
    return PERSONALITY

async def personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Качества"] = update.message.text
    await update.message.reply_text("Что допустимо в работе?")
    return LIMITS

async def limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Границы"] = update.message.text
    
    # Формируем текст
    summary = "📋 НОВАЯ АНКЕТА:\n\n"
    for k, v in context.user_data.items():
        if k != "Фото": summary += f"{k}: {v}\n"

    # Отправка
    await update.message.reply_text("Отправляю анкету...")
    if send_email(f"Анкета: {context.user_data.get('ФИО')}", summary):
        await update.message.reply_text("✅ Успешно отправлено на почту!")
    else:
        await update.message.reply_text("❌ Ошибка почты. Свяжитесь с админом.")
    
    return ConversationHandler.END

def main():
    if not TOKEN: 
        print("Ошибка: BOT_TOKEN не найден!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fio)],
            DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, dob)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email)],
            DOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, doc)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight)],
            CLOTHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, clothes)],
            BREAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, breast)],
            HAIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, hair)],
            EYES: [MessageHandler(filters.TEXT & ~filters.COMMAND, eyes)],
            TATTOO: [MessageHandler(filters.TEXT & ~filters.COMMAND, tattoo)],
            PHOTOS: [MessageHandler(filters.PHOTO, photos)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, experience)],
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, hours)],
            DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, days)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time)],
            PERSONALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, personality)],
            LIMITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, limits)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(conv)
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
