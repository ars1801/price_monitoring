from decimal import Decimal
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.models import PriceHistory, ProductSource, Source, Product


@dataclass(slots=True, frozen=True)
class PriceChangeCandidate:
    product_source_id: int
    product_id: int
    product_name: str
    product_brand: str | None
    source_name: str
    product_url: str
    started_at: datetime
    ended_at: datetime
    start_price: Decimal
    end_price: Decimal
    delta_percent: Decimal

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
    
    def get_significant_product_source_changes(
        self,
        *,
        period_start: datetime,
        min_abs_change_percent: Decimal,
        latest_after: datetime | None = None,
    ) -> list[PriceChangeCandidate]:
        product_source_rows = self._db.execute(
            select(
                ProductSource.id,
                Product.id,
                Product.name,
                Product.brand,
                Source.name,
                ProductSource.product_url,
            )
            .join(Product, Product.id == ProductSource.product_id)
            .join(Source, Source.id == ProductSource.source_id)
            .where(ProductSource.is_active.is_(True))
        ).all()

        candidates: list[PriceChangeCandidate] = []
        for product_source_id, product_id, product_name, product_brand, source_name, product_url in product_source_rows:
            first_record = self._db.scalar(
                select(PriceHistory)
                .where(
                    PriceHistory.product_source_id == product_source_id,
                    PriceHistory.created_at >= period_start,
                )
                .order_by(asc(PriceHistory.created_at), asc(PriceHistory.id))
                .limit(1)
            )
            last_record = self._db.scalar(
                select(PriceHistory)
                .where(
                    PriceHistory.product_source_id == product_source_id,
                    PriceHistory.created_at >= period_start,
                )
                .order_by(desc(PriceHistory.created_at), desc(PriceHistory.id))
                .limit(1)
            )

            if first_record is None or last_record is None:
                continue

            if first_record.id == last_record.id:
                continue

            start_price = Decimal(first_record.price)
            end_price = Decimal(last_record.price)
            if start_price == 0:
                continue

            if latest_after is not None:
                last_created_at = (
                    last_record.created_at
                    if last_record.created_at.tzinfo is not None
                    else last_record.created_at.replace(tzinfo=UTC)
                )
                if last_created_at < latest_after:
                    continue

            delta_percent = ((end_price - start_price) / start_price) * Decimal("100")
            if abs(delta_percent) < min_abs_change_percent:
                continue

            candidates.append(
                PriceChangeCandidate(
                    product_source_id=product_source_id,
                    product_id=product_id,
                    product_name=product_name,
                    product_brand=product_brand,
                    source_name=source_name,
                    product_url=product_url,
                    started_at=first_record.created_at,
                    ended_at=last_record.created_at,
                    start_price=start_price,
                    end_price=end_price,
                    delta_percent=delta_percent,
                )
            )

        return candidates