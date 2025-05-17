from telegram.ext import (
    Application,
    PreCheckoutQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from settings import BOT_TOKEN
from telegram_bot import BotController


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    controller = BotController()

    application.add_handler(CommandHandler("start", controller.start))
    application.add_handler(CommandHandler("help", controller.help))
    application.add_handler(PreCheckoutQueryHandler(controller.pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, controller.payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, controller.feedback))

    application.run_polling()

if __name__ == "__main__":
    main()