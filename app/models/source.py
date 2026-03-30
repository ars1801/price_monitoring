from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Source(Base):
    # Справочник магазинов / источников данных.
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Связи магазина с конкретными карточками товаров.
    product_sources: Mapped[list["ProductSource"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )