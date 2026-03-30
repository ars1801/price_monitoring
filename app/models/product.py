from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Product(Base):
    # Общая сущность товара без привязки к конкретному магазину.
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Связи товара с магазинами и карточками товаров.
    product_sources: Mapped[list["ProductSource"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )