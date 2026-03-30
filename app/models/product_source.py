from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProductSource(Base):
    # Связь товара с конкретным магазином.
    # Здесь храним URL карточки товара и дополнительные данные источника.
    __tablename__ = "product_sources"

    __table_args__ = (
        UniqueConstraint("source_id", "product_url", name="uq_product_sources_source_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    product: Mapped["Product"] = relationship(back_populates="product_sources")
    source: Mapped["Source"] = relationship(back_populates="product_sources")

    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="product_source",
        cascade="all, delete-orphan",
    )