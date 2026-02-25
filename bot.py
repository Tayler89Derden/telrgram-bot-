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

# ─── НАСТРОЙКИ ───────────────────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Состояния анкеты (19 штук)
FIO, DOB, CITY, CONTACT, EMAIL, DOC, HEIGHT, WEIGHT, CLOTHES, BREAST, \
    HAIR, EYES, TATTOO, PHOTOS, EXPERIENCE, HOURS, DAYS, TIME, LIMITS = range(19)


def send_email(subject: str, body: str) -> bool:
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("!!! Отсутствуют переменные окружения для email")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

        print("Email успешно отправлен")
        return True

    except Exception as e:
        print(f"!!! ОШИБКА ОТПРАВКИ EMAIL: {type(e).__name__}: {e}")
        return False


# ─── ХЕНДЛЕРЫ ────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Привет! Давай заполним анкету.\n\nНапиши своё ФИО полностью:",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()  # чистим на всякий случай
    return FIO


async def fio_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ФИО"] = update.message.text.strip()
    await update.message.reply_text("Дата рождения (например: 15.03.2001):")
    return DOB


async def dob_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Дата рождения"] = update.message.text.strip()
    await update.message.reply_text("Город проживания:")
    return CITY


async def city_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Город"] = update.message.text.strip()
    await update.message.reply_text("Контактный телефон / Telegram:")
    return CONTACT


async def contact_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Контакт"] = update.message.text.strip()
    await update.message.reply_text("Email:")
    return EMAIL


async def email_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Email"] = update.message.text.strip()
    await update.message.reply_text("Номер и серия паспорта / другого документа (если не хочешь — напиши '-'):")
    return DOC


async def doc_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Документ"] = update.message.text.strip()
    await update.message.reply_text("Рост (см):")
    return HEIGHT


async def height_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Рост"] = update.message.text.strip()
    await update.message.reply_text("Вес (кг):")
    return WEIGHT


async def weight_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Вес"] = update.message.text.strip()
    await update.message.reply_text("Размер одежды:")
    return CLOTHES


async def clothes_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Одежда"] = update.message.text.strip()
    await update.message.reply_text("Размер груди:")
    return BREAST


async def breast_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Грудь"] = update.message.text.strip()
    await update.message.reply_text("Цвет и длина волос:")
    return HAIR


async def hair_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Волосы"] = update.message.text.strip()
    await update.message.reply_text("Цвет глаз:")
    return EYES


async def eyes_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Глаза"] = update.message.text.strip()
    await update.message.reply_text("Есть ли татуировки / пирсинг? (опиши или напиши нет):")
    return TATTOO


async def tattoo_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Тату / пирсинг"] = update.message.text.strip()
    await update.message.reply_text("Отправь фото (можно несколько, по одному или сразу пачкой):")
    return PHOTOS


async def photos_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Просто считаем, что фото пришли — сохранять их не будем
    photos_count = len(update.message.photo)
    context.user_data["Фото"] = f"{photos_count} шт. отправлено"
    await update.message.reply_text("Опыт работы (можно кратко):")
    return EXPERIENCE


async def experience_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Опыт"] = update.message.text.strip()
    await update.message.reply_text("Сколько часов в сутки готова работать?")
    return HOURS


async def hours_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Часы в сутки"] = update.message.text.strip()
    await update.message.reply_text("Какие дни недели удобны? (можно несколько)")
    return DAYS


async def days_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Дни"] = update.message.text.strip()
    kb = [["Утро", "День"], ["Вечер", "Ночь"]]
    await update.message.reply_text(
        "Предпочтительное время суток:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return TIME


async def time_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Время"] = update.message.text.strip()
    await update.message.reply_text(
        "Что допустимо / недопустимо в работе? (опиши подробно)",
        reply_markup=ReplyKeyboardRemove()
    )
    return LIMITS


async def limits_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Допустимое / ограничения"] = update.message.text.strip()

    # Формируем красивое письмо
    summary = "📋 НОВАЯ АНКЕТА\n" + "═" * 40 + "\n"
    for key, value in context.user_data.items():
        if key != "Фото":
            summary += f" {key:<18} : {value}\n"
    summary += f" Фото            : {context.user_data.get('Фото', 'нет')}\n"
    summary += "═" * 40 + "\n"

    success = send_email(
        subject=f"Анкета — {context.user_data.get('ФИО', 'Без имени')}",
        body=summary
    )

    if success:
        await update.message.reply_text("✅ Анкета успешно отправлена!\nСпасибо!")
    else:
        await update.message.reply_text(
            "⚠️ Не удалось отправить анкету на почту.\n"
            "Администратор уже уведомлён (скорее всего проблема в настройках)."
        )

    # Можно очистить данные после отправки
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Анкета отменена.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─── ЗАПУСК ──────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        print("!!! BOT_TOKEN не задан в переменных окружения")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FIO:        [MessageHandler(filters.TEXT & ~filters.COMMAND, fio_step)],
            DOB:        [MessageHandler(filters.TEXT & ~filters.COMMAND, dob_step)],
            CITY:       [MessageHandler(filters.TEXT & ~filters.COMMAND, city_step)],
            CONTACT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_step)],
            EMAIL:      [MessageHandler(filters.TEXT & ~filters.COMMAND, email_step)],
            DOC:        [MessageHandler(filters.TEXT & ~filters.COMMAND, doc_step)],
            HEIGHT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, height_step)],
            WEIGHT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, weight_step)],
            CLOTHES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, clothes_step)],
            BREAST:     [MessageHandler(filters.TEXT & ~filters.COMMAND, breast_step)],
            HAIR:       [MessageHandler(filters.TEXT & ~filters.COMMAND, hair_step)],
            EYES:       [MessageHandler(filters.TEXT & ~filters.COMMAND, eyes_step)],
            TATTOO:     [MessageHandler(filters.TEXT & ~filters.COMMAND, tattoo_step)],
            PHOTOS:     [MessageHandler(filters.PHOTO, photos_step)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, experience_step)],
            HOURS:      [MessageHandler(filters.TEXT & ~filters.COMMAND, hours_step)],
            DAYS:       [MessageHandler(filters.TEXT & ~filters.COMMAND, days_step)],
            TIME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, time_step)],
            LIMITS:     [MessageHandler(filters.TEXT & ~filters.COMMAND, limits_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)

    print("Бот запущен. polling...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
