from telegram import Update, User

from suppgram.entities import WorkplaceIdentification, AgentIdentification


def make_agent_identification(effective_user: User) -> AgentIdentification:
    return AgentIdentification(telegram_user_id=effective_user.id)


def make_workplace_identification(
    update: Update, effective_user: User
) -> WorkplaceIdentification:
    return WorkplaceIdentification(
        telegram_user_id=effective_user.id,
        telegram_bot_id=update.get_bot().id,
    )
