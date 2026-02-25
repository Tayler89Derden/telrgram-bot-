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

# Состояния анкеты (19)
FIO, DOB, CITY, CONTACT, EMAIL, DOC, HEIGHT, WEIGHT, CLOTHES, BREAST, \
    HAIR, EYES, TATTOO, PHOTOS, EXPERIENCE, HOURS, DAYS, TIME, LIMITS = range(19)


def send_email(subject: str, body: str) -> bool:
    print("[EMAIL DEBUG] === Начало отправки email ===")
    print(f"[EMAIL DEBUG] Sender: {EMAIL_SENDER or 'НЕ ЗАДАН!!!'}")
    print(f"[EMAIL DEBUG] Receiver: {EMAIL_RECEIVER or 'НЕ ЗАДАН!!!'}")
    print(f"[EMAIL DEBUG] Password length: {len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 'ПУСТОЙ!!!'} chars")
    
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("[EMAIL ERROR] Отсутствует хотя бы одна переменная окружения для email")
        return False

    try:
        import socket
        print("[EMAIL DEBUG] Тест соединения к smtp.gmail.com:465...")
        socket.create_connection(("smtp.gmail.com", 465), timeout=10)
        print("[EMAIL DEBUG] Сокет-соединение открыто успешно!")

        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        print("[EMAIL DEBUG] Создаём SMTP_SSL соединение...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            print("[EMAIL DEBUG] Попытка login...")
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            print("[EMAIL DEBUG] Login успешен")
            print("[EMAIL DEBUG] Отправка сообщения...")
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
            print("[EMAIL DEBUG] sendmail завершён без исключений")
        
        print("[EMAIL DEBUG] === Email успешно отправлен (сервер принял) ===")
        return True

    except Exception as e:
        print(f"[EMAIL CRITICAL] ОШИБКА: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ─── ШАГИ АНКЕТЫ ─────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print(f"[DEBUG] /start от {update.effective_user.id}")
    await update.message.reply_text(
        "Привет! Заполним анкету.\n\nФИО полностью:",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return FIO


async def fio_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ФИО"] = update.message.text.strip()
    await update.message.reply_text("Дата рождения (дд.мм.гггг):")
    return DOB


async def dob_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Дата рождения"] = update.message.text.strip()
    await update.message.reply_text("Город:")
    return CITY


async def city_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Город"] = update.message.text.strip()
    await update.message.reply_text("Контакт (телефон / Telegram):")
    return CONTACT


async def contact_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Контакт"] = update.message.text.strip()
    await update.message.reply_text("Email:")
    return EMAIL


async def email_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Email"] = update.message.text.strip()
    await update.message.reply_text("Документ (паспорт или '-'):")
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
    await update.message.reply_text("Волосы (цвет + длина):")
    return HAIR


async def hair_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Волосы"] = update.message.text.strip()
    await update.message.reply_text("Глаза (цвет):")
    return EYES


async def eyes_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Глаза"] = update.message.text.strip()
    await update.message.reply_text("Тату / пирсинг (опиши или 'нет'):")
    return TATTOO


async def tattoo_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Тату / пирсинг"] = update.message.text.strip()
    await update.message.reply_text("Отправь фото (можно несколько):")
    return PHOTOS


async def photos_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print(f"[DEBUG] photos_step вызван, user={update.effective_user.id}")
    
    if update.message.photo:
        count = len(update.message.photo)
        context.user_data["Фото"] = f"{count} фото"
        print(f"[DEBUG] Обработано {count} фото")
    elif update.message.document:
        context.user_data["Фото"] = "Документ(ы) отправлен(ы)"
        print("[DEBUG] Обработан документ")
    else:
        context.user_data["Фото"] = "Медиа получено"
        print("[DEBUG] Неизвестный тип медиа")

    await update.message.reply_text("Фото принято!\n\nОпыт работы (кратко):")
    return EXPERIENCE


async def experience_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Опыт"] = update.message.text.strip()
    await update.message.reply_text("Сколько часов в сутки готова работать?")
    return HOURS


async def hours_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Часы"] = update.message.text.strip()
    await update.message.reply_text("Какие дни удобны?")
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
        "Что допустимо / недопустимо в работе? (подробно)",
        reply_markup=ReplyKeyboardRemove()
    )
    return LIMITS


async def limits_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["Ограничения"] = update.message.text.strip()

    summary = "📋 АНКЕТА\n" + "═" * 50 + "\n"
    for k, v in context.user_data.items():
        if k != "Фото":
            summary += f"{k:<18}: {v}\n"
    summary += f"Фото            : {context.user_data.get('Фото', 'нет')}\n"
    summary += "═" * 50

    success = send_email(
        f"Анкета — {context.user_data.get('ФИО', 'Без имени')}",
        summary
    )

    if success:
        await update.message.reply_text("✅ Анкета отправлена на почту! Спасибо!")
    else:
        await update.message.reply_text(
            "⚠️ Не удалось отправить анкету на почту.\n"
            "Проверь логи Render — там детальная диагностика.\n"
            "Данные анкеты ниже (не потеряны):"
        )
        await update.message.reply_text(summary)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Анкета отменена.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END


# ─── ЗАПУСК ──────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        print("!!! BOT_TOKEN отсутствует → выход")
        return

    print("[START] BOT_TOKEN найден, длина:", len(TOKEN))
    print("[START] Запуск бота...")

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
            PHOTOS: [MessageHandler(filters.PHOTO | filters.Document.ALL, photos_step)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, experience_step)],
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, hours_step)],
            DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, days_step)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time_step)],
            LIMITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, limits_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
