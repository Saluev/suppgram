from telegram import Update

from suppgram.entities import WorkplaceIdentification, AgentIdentification


def make_agent_identification(update: Update) -> AgentIdentification:
    return AgentIdentification(telegram_user_id=update.effective_user.id)


def make_workplace_identification(update: Update) -> WorkplaceIdentification:
    return WorkplaceIdentification(
        telegram_user_id=update.effective_user.id,
        telegram_bot_id=update.get_bot().id,
    )
