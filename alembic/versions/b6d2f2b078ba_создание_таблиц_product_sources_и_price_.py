"""создание таблиц product sources и price histry table

Revision ID: b6d2f2b078ba
Revises: 437e46b9bcce
Create Date: 2026-03-31 01:38:19.754253

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6d2f2b078ba'
down_revision: Union[str, Sequence[str], None] = '437e46b9bcce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "product_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("product_url", sa.String(length=1000), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),

        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),

        sa.UniqueConstraint("source_id", "product_url", name="uq_product_sources_source_url"),
    )

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_source_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),

        sa.ForeignKeyConstraint(
            ["product_source_id"],
            ["product_sources.id"],
            ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("price_history")
    op.drop_table("product_sources")
    op.drop_table("sources")
    op.drop_table("products")