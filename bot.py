import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

(
    FIO, DOB, CITY, CONTACT, EMAIL, DOC,
    HEIGHT, WEIGHT, CLOTHES, BREAST, HAIR, EYES, TATTOO, PHOTOS,
    EXPERIENCE, CAMERA, HOURS, DAYS, TIME, EQUIPMENT,
    PERSONALITY, LIMITS, SUMMARY
) = range(23)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Введите ФИО:")
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
    await update.message.reply_text("Телефон / Telegram / WhatsApp:")
    return CONTACT


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Контакт"] = update.message.text
    await update.message.reply_text("Email:")
    return EMAIL


async def email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Email"] = update.message.text
    keyboard = [["Да", "Нет"]]
    await update.message.reply_text(
        "Документ подтверждающий возраст?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
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
    await update.message.reply_text("Есть ли тату/пирсинг? (описать):")
    return TATTOO


async def tattoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Тату/пирсинг"] = update.message.text
    context.user_data["Фото"] = []
    await update.message.reply_text("Пришлите 3–5 фото без фильтров (лицо + полный рост).")
    return PHOTOS


async def photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["Фото"].append(update.message.photo[-1].file_id)

    if len(context.user_data["Фото"]) >= 3:
        await update.message.reply_text("Был ли опыт? (опишите)")
        return EXPERIENCE
    else:
        await update.message.reply_text(f"Получено {len(context.user_data['Фото'])} фото. Нужно минимум 3.")
        return PHOTOS


async def experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Опыт"] = update.message.text
    await update.message.reply_text("Сколько часов в день готовы работать?")
    return HOURS


async def hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Часы"] = update.message.text
    await update.message.reply_text("Сколько дней в неделю?")
    return DAYS


async def days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Дни"] = update.message.text
    keyboard = [["Утро", "День", "Вечер", "Ночь"]]
    await update.message.reply_text(
        "Предпочитаемое время:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return TIME


async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Время"] = update.message.text
    await update.message.reply_text("Опишите личные качества:")
    return PERSONALITY


async def personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Личные качества"] = update.message.text
    await update.message.reply_text("Что допустимо в работе? (опишите)")
    return LIMITS


async def limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["Границы"] = update.message.text

    summary = "\n\n📋 Ваша анкета:\n\n"
    for key, value in context.user_data.items():
        if key != "Фото":
            summary += f"{key}: {value}\n"

    await update.message.reply_text(summary, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text("Спасибо! Анкета отправлена.")

    return ConversationHandler.END


async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Начинаем редактирование заново.")
    return await start(update, context)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("edit", edit)],
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
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
