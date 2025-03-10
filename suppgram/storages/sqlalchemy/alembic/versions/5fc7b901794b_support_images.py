"""Support images

Revision ID: 5fc7b901794b
Revises: 48f9a7635310
Create Date: 2025-03-08 14:16:07.810681

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5fc7b901794b"
down_revision = "48f9a7635310"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "suppgram_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "AGENT_ASSIGNED",
                "CONVERSATION_POSTPONED",
                "CONVERSATION_RATED",
                "CONVERSATION_RESOLVED",
                "CONVERSATION_STARTED",
                "CONVERSATION_TAG_ADDED",
                "CONVERSATION_TAG_REMOVED",
                "MESSAGE_SENT",
                name="eventkind",
            ),
            nullable=False,
        ),
        sa.Column("time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column(
            "message_kind",
            sa.Enum("FROM_CUSTOMER", "FROM_AGENT", "POSTPONED", "RESOLVED", name="messagekind"),
            nullable=True,
        ),
        sa.Column(
            "message_media_kind",
            sa.Enum("NONE", "TEXT", "IMAGE", name="messagemediakind"),
            nullable=True,
        ),
        sa.Column("tag_id", sa.Integer(), nullable=True),
        sa.Column("workplace_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["suppgram_agents.id"],
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["suppgram_conversations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["suppgram_customers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["suppgram_tags.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workplace_id"],
            ["suppgram_workplaces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "suppgram_conversation_messages", sa.Column("image", sa.LargeBinary(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("suppgram_conversation_messages", "image")
    op.drop_table("suppgram_events")
    # ### end Alembic commands ###
