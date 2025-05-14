import hashlib
import hmac
from urllib.parse import parse_qs, unquote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, PreCheckoutQueryHandler, CommandHandler, CallbackContext, MessageHandler, filters

from db.base import AsyncSessionFactory
from db import UserManager
from settings import BOT_TOKEN, WEB_APP_URL, ADMIN_ID

TELEGRAM_BOT_SECRET = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()

application = Application.builder().token(BOT_TOKEN).build()

def check_telegram_signature(init_data):
    parsed_data = parse_qs(init_data)
    hash_received = parsed_data.pop("hash", [""])[0].strip()
    if not hash_received:
        return False
    data_check_string = "\n".join(
        f"{key}={unquote(value[0])}" for key, value in sorted(parsed_data.items())
    )
    computed_hash = hmac.new(TELEGRAM_BOT_SECRET, data_check_string.encode(), hashlib.sha256).hexdigest()
    return computed_hash == hash_received


async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton(
                "Открыть мини-приложение", web_app={"url": WEB_APP_URL}
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎬 *Добро пожаловать в MovieAI!*\n\n"
        "Подберите фильм по описанию, настроению или жанру — с помощью приложения.\n\n"
        "Отправьте /help, чтобы узнать обо всех возможностях.\n\n"
        "Нажмите кнопку ниже, чтобы начать.\n\n",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "❓ *Что умеет MovieAI*\n\n"
        "Вы можете выбрать удобный способ поиска фильмов:\n"
        "•  По жанру, атмосфере, году и другим фильтрам\n"
        "•  По вашему описанию — в интерактивном чате\n"
        "•  По понравившемуся фильму — найдёт похожие\n\n"
        "❤️ В подборе — добавляйте фильмы в избранное, чтобы не потерять лучшие находки.\n\n"
        "У вас есть идея, вопрос или предложение? \nПросто напишите в сообщении боту — он всё читает!\n\n"
        "Нажмите /start, чтобы открыть мини-приложение\n\n",
        parse_mode="Markdown"
    )

async def pre_checkout_handler(update: Update, context: CallbackContext):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def message_handler(update: Update, context: CallbackContext) -> None:
    bot = context.bot
    msg = update.message
    user_id = msg.chat.id

    if msg and msg.text:
        feedback_text = f"🗣 Сообщение от пользователя @{msg.from_user.username} ({user_id}):\n\n{msg.text}"
        await bot.send_message(chat_id=ADMIN_ID, text=feedback_text)
        await msg.reply_text("Спасибо за обратную связь! Мы всё учтём 🙌")

    #charge_id = msg.text
    #await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)

async def successful_payment_handler(
        update: Update,
        context: CallbackContext
)  -> None:
    payment = update.message.successful_payment
    user_id = update.message.chat.id

    provider_payment_charge_id = payment.provider_payment_charge_id
    telegram_payment_charge_id = payment.telegram_payment_charge_id
    total_amount = payment.total_amount
    currency = payment.currency

    async with AsyncSessionFactory() as session:
        async with session.begin():
            user_manager = UserManager(session=session)
            saved = await user_manager.save_payment(
                user_id=user_id,
                provider_payment_charge_id=provider_payment_charge_id,
                telegram_payment_charge_id=telegram_payment_charge_id,
                total_amount=total_amount,
                currency=currency
            )
            if saved:
                await user_manager.update_balance(user_id=user_id, delta=total_amount)

    await context.bot.send_message(
        chat_id=user_id,
        text=f"🎉 Платёж прошёл успешно! Тебе начислено {total_amount} звезд ⭐️"
    )

def main():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    application.add_handler(MessageHandler(filters.ALL, message_handler))
    application.run_polling()

if __name__ == "__main__":
    main()