from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PriceHistory(Base):
    # История цен по конкретной карточке товара в конкретном магазине.
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    product_source_id: Mapped[int] = mapped_column(
        ForeignKey("product_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    product_source: Mapped["ProductSource"] = relationship(back_populates="price_history")