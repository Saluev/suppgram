from telegram import Update, User

from suppgram.entities import (
    WorkplaceIdentification,
    AgentIdentification,
    CustomerIdentification,
    AgentDiff,
    CustomerDiff,
)


def make_agent_identification(effective_user: User) -> AgentIdentification:
    return AgentIdentification(telegram_user_id=effective_user.id)


def make_agent_diff(effective_user: User) -> AgentDiff:
    return AgentDiff(
        telegram_first_name=effective_user.first_name,
        telegram_last_name=effective_user.last_name,
        telegram_username=effective_user.username,
    )


def make_customer_identification(effective_user: User) -> CustomerIdentification:
    return CustomerIdentification(telegram_user_id=effective_user.id)


def make_customer_diff(effective_user: User) -> CustomerDiff:
    return CustomerDiff(
        telegram_first_name=effective_user.first_name,
        telegram_last_name=effective_user.last_name,
        telegram_username=effective_user.username,
    )


def make_workplace_identification(
    update: Update, effective_user: User
) -> WorkplaceIdentification:
    return WorkplaceIdentification(
        telegram_user_id=effective_user.id,
        telegram_bot_id=update.get_bot().id,
    )
