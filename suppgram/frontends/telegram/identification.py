from telegram import Update

from suppgram.entities import WorkplaceIdentification


def make_workplace_identification(update: Update) -> WorkplaceIdentification:
    return WorkplaceIdentification(
        telegram_user_id=update.effective_user.id,
        telegram_bot_id=update.get_bot().id,
        telegram_chat_id=update.effective_chat.id,
    )
