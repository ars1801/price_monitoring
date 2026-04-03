from decimal import Decimal
from datetime import UTC, datetime, timedelta

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.models import PriceHistory, ProductSource, Source


class PriceHistoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, *, product_source: ProductSource, price: Decimal) -> PriceHistory:
        entity = PriceHistory(product_source=product_source, price=price)
        self._db.add(entity)
        return entity
    
    def add_if_changed_or_snapshot(
        self,
        *,
        product_source: ProductSource,
        price: Decimal,
        snapshot_interval_minutes: int,
    ) -> bool:
        last_record = self._db.scalar(
            select(PriceHistory)
            .where(PriceHistory.product_source_id == product_source.id)
            .order_by(desc(PriceHistory.created_at), desc(PriceHistory.id))
            .limit(1)
        )

        if last_record is None:
            self.add(product_source=product_source, price=price)
            return True

        if last_record.price != price:
            self.add(product_source=product_source, price=price)
            return True

        if snapshot_interval_minutes <= 0:
            return False

        now = datetime.now(UTC)
        last_created_at = (
            last_record.created_at
            if last_record.created_at.tzinfo is not None
            else last_record.created_at.replace(tzinfo=UTC)
        )
        if now - last_created_at >= timedelta(minutes=snapshot_interval_minutes):
            self.add(product_source=product_source, price=price)
            return True

        return False
    
    def get_product_price_history(self, *, product_id: int) -> list[dict[str, object]]:
        rows = self._db.execute(
            select(PriceHistory, ProductSource, Source)
            .join(ProductSource, ProductSource.id == PriceHistory.product_source_id)
            .join(Source, Source.id == ProductSource.source_id)
            .where(ProductSource.product_id == product_id)
            .order_by(asc(PriceHistory.created_at), asc(PriceHistory.id))
        ).all()

        return [
            {
                "price": price_history.price,
                "created_at": price_history.created_at,
                "source": source.name,
                "product_url": product_source.product_url,
                "category": product_source.category,
            }
            for price_history, product_source, source in rows
        ]

    def get_period_bounds(
        self,
        *,
        product_id: int,
        period_start: datetime,
    ) -> tuple[PriceHistory | None, PriceHistory | None]:
        first_record = self._db.scalar(
            select(PriceHistory)
            .join(ProductSource, ProductSource.id == PriceHistory.product_source_id)
            .where(
                ProductSource.product_id == product_id,
                PriceHistory.created_at >= period_start,
            )
            .order_by(asc(PriceHistory.created_at), asc(PriceHistory.id))
            .limit(1)
        )
        last_record = self._db.scalar(
            select(PriceHistory)
            .join(ProductSource, ProductSource.id == PriceHistory.product_source_id)
            .where(
                ProductSource.product_id == product_id,
                PriceHistory.created_at >= period_start,
            )
            .order_by(desc(PriceHistory.created_at), desc(PriceHistory.id))
            .limit(1)
        )
        return first_record, last_record