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

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Явно задаем состояния, чтобы не запутаться в числах
FIO, DOB, CITY, CONTACT, EMAIL, DOC, HEIGHT, WEIGHT, CLOTHES, BREAST, \
HAIR, EYES, TATTOO, PHOTOS, EXPERIENCE, HOURS, DAYS, TIME, PERSONALITY, LIMITS = range(20)

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        return True
    except Exception as e:
        print(f"Ошибка почты: {e}")
        return False

# --- ФУНКЦИИ-ШАГИ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Начинаем анкетирование.\nВведите Ваше ФИО:")
    return FIO

async def fio_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ФИО"] = update.message.text
    await update.message.reply_text("Дата рождения:")
    return DOB

async def dob_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Дата рождения"] = update.message.text
    await update.message.reply_text("Город проживания:")
    return CITY

async def city_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Город"] = update.message.text
    await update.message.reply_text("Ваш контакт (Телефон/Ник):")
    return CONTACT

async def contact_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Контакт"] = update.message.text
    await update.message.reply_text("Ваш Email:")
    return EMAIL

async def email_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Email"] = update.message.text
    kb = [["Да", "Нет"]]
    await update.message.reply_text("Есть документ, подтверждающий возраст?", 
                                   reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return DOC

async def doc_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Документ"] = update.message.text
    await update.message.reply_text("Рост:", reply_markup=ReplyKeyboardRemove())
    return HEIGHT

async def height_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Рост"] = update.message.text
    await update.message.reply_text("Вес:")
    return WEIGHT

async def weight_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Вес"] = update.message.text
    await update.message.reply_text("Размер одежды:")
    return CLOTHES

async def clothes_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Одежда"] = update.message.text
    await update.message.reply_text("Размер груди:")
    return BREAST

async def breast_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Грудь"] = update.message.text
    await update.message.reply_text("Цвет волос:")
    return HAIR

async def hair_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Волосы"] = update.message.text
    await update.message.reply_text("Цвет глаз:")
    return EYES

async def eyes_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Глаза"] = update.message.text
    await update.message.reply_text("Тату / Пирсинг:")
    return TATTOO

async def tattoo_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Тату"] = update.message.text
    context.user_data["Фото"] = []
    await update.message.reply_text("Пришлите 3 фото (лицо, рост, фильтры нельзя). Жду первое:")
    return PHOTOS

async def photos_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["Фото"].append(update.message.photo[-1].file_id)
    
    current_count = len(context.user_data["Фото"])
    if current_count < 3:
        await update.message.reply_text(f"Загружено {current_count}/3. Жду следующее фото:")
        return PHOTOS
    
    await update.message.reply_text("Опыт работы (опишите):")
    return EXPERIENCE

async def experience_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Опыт"] = update.message.text
    await update.message.reply_text("Сколько часов в день готовы работать?")
    return HOURS

async def hours_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Часы"] = update.message.text
    await update.message.reply_text("Сколько дней в неделю?")
    return DAYS

async def days_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Дни"] = update.message.text
    kb = [["Утро", "День", "Вечер", "Ночь"]]
    await update.message.reply_text("Предпочтительное время:", 
                                   reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return TIME

async def time_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Время"] = update.message.text
    await update.message.reply_text("Личные качества:", reply_markup=ReplyKeyboardRemove())
    return PERSONALITY

async def personality_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Личные качества"] = update.message.text
    await update.message.reply_text("Что допустимо в работе?")
    return LIMITS

async def limits_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Допустимое"] = update.message.text
    
    # Сборка анкеты
    summary = "📋 НОВАЯ АНКЕТА\n" + "="*20 + "\n"
    for key, value in context.user_data.items():
        if key != "Фото":
            summary += f"🔹 {key}: {value}\n"

    await update.message.reply_text("Спасибо! Отправляю вашу анкету...")
    
    if send_email(f"Анкета: {context.user_data.get('ФИО')}", summary):
        await update.message.reply_text("✅ Анкета доставлена! Мы свяжемся с вами.")
    else:
        await update.message.reply_text("⚠️ Ошибка отправки на почту, но анкета сохранена в базе.")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Заполнение прервано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- ЗАПУСК ---
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
            PERSONALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, personality_step)],
            LIMITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, limits_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    print("Бот в эфире...")
    app.run_polling()

if __name__ == "__main__":
    main()
