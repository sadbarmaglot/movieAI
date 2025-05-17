from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)
from telegram.ext import CallbackContext

from db_managers import UserManager, with_user_manager
from settings import (
    ADMIN_ID,
    WEB_APP_URL,
    BUTTON_TEXT,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    FEEDBACK_MASSAGE,
    PAYMENT_MESSAGE
)


class BotController:
    def __init__(
            self,
            admin_id: int = ADMIN_ID,
            web_app_url: str = WEB_APP_URL,
            button_text: dict = BUTTON_TEXT,
            welcome_message: dict = WELCOME_MESSAGE,
            help_message: dict = HELP_MESSAGE,
            feedback_message: dict = FEEDBACK_MASSAGE,
            payment_message: dict = PAYMENT_MESSAGE
    ):
        self.admin_id = admin_id
        self.web_app_url = web_app_url
        self.button_text = button_text
        self.welcome_message = welcome_message
        self.help_message = help_message
        self.feedback_message = feedback_message
        self.payment_message = payment_message

    @staticmethod
    def _lang(update: Update) -> str:
        return "ru" if update.effective_user.language_code.startswith("ru") else "en"

    @staticmethod
    async def _reply(
            update: Update,
            text: str,
            parse_mode: str ="Markdown",
            reply_markup=None
    ) -> None:
        await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)

    async def start(self, update: Update, context: CallbackContext) -> None:
        if update.message is None:
            return
        lang = self._lang(update)

        keyboard = [
            [
                InlineKeyboardButton(
                    self.button_text[lang],
                    web_app=WebAppInfo(url=self.web_app_url),
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._reply(
            update=update,
            text=self.welcome_message[lang],
            reply_markup=reply_markup
        )

    async def help(self, update: Update, context: CallbackContext) -> None:
        if update.message is None:
            return
        lang = self._lang(update)

        await self._reply(
            update=update,
            text=self.help_message[lang],
        )

    async def feedback(self, update: Update, context: CallbackContext) -> None:
        msg = update.message
        if msg is None:
            return

        user_id = msg.chat.id
        lang = self._lang(update)
        bot = context.bot
        username = msg.from_user.username or "no username"

        if msg and msg.text:
            feedback_text = f"🗣 Сообщение от пользователя {username} ({user_id}):\n\n{msg.text}"
            await bot.send_message(chat_id=self.admin_id, text=feedback_text)
            await self._reply(
                update=update,
                text=self.feedback_message[lang],
            )
        # await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)

    @staticmethod
    async def pre_checkout(update: Update, context: CallbackContext):
        query = update.pre_checkout_query
        await query.answer(ok=True)

    @with_user_manager
    async def _payment(self, update: Update, context: CallbackContext, user_manager: UserManager) -> None:
        if update.message is None:
            return
        lang = self._lang(update)

        payment = update.message.successful_payment
        user_id = update.message.chat.id
        provider_payment_charge_id = payment.provider_payment_charge_id
        telegram_payment_charge_id = payment.telegram_payment_charge_id
        total_amount = payment.total_amount
        currency = payment.currency

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
            text=self.payment_message[lang](total_amount)
        )

    async def payment(self, update: Update, context: CallbackContext) -> None:
        await self._payment(update, context)
