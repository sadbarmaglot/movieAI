import hashlib
import hmac
from urllib.parse import parse_qs, unquote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, PreCheckoutQueryHandler, CommandHandler, CallbackContext, MessageHandler, filters

from db_managers import AsyncSessionFactory, UserManager
from settings import (
    BOT_TOKEN,
    WEB_APP_URL,
    ADMIN_ID,
    BUTTON_TEXT,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    FEEDBACK_MASSAGE,
    PAYMENT_MESSAGE,
)

TELEGRAM_BOT_SECRET = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()

application = Application.builder().token(BOT_TOKEN).build()

def get_user_lang(update: Update) -> str:
    lang = update.effective_user.language_code
    return "ru" if lang and lang.startswith("ru") else "en"

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
    lang = get_user_lang(update)

    keyboard = [
        [
            InlineKeyboardButton(
                BUTTON_TEXT[lang], web_app={"url": WEB_APP_URL} # type: ignore
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        WELCOME_MESSAGE[lang],
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    lang = get_user_lang(update)
    await update.message.reply_text(
        HELP_MESSAGE[lang],
        parse_mode="Markdown"
    )

async def pre_checkout_handler(update: Update, context: CallbackContext):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def message_handler(update: Update, context: CallbackContext) -> None:
    lang = get_user_lang(update)

    bot = context.bot
    msg = update.message
    user_id = msg.chat.id

    if msg and msg.text:
        feedback_text = f"🗣 Сообщение от пользователя @{msg.from_user.username} ({user_id}):\n\n{msg.text}"
        await bot.send_message(chat_id=ADMIN_ID, text=feedback_text)
        await msg.reply_text(FEEDBACK_MASSAGE[lang])

    #charge_id = msg.text
    #await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)

async def successful_payment_handler(
        update: Update,
        context: CallbackContext
)  -> None:
    lang = get_user_lang(update)

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
        text=PAYMENT_MESSAGE[lang](total_amount)
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