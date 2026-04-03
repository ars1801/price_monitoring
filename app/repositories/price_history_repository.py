from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import PriceHistory, ProductSource


class PriceHistoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, *, product_source: ProductSource, price: Decimal) -> PriceHistory:
        entity = PriceHistory(product_source=product_source, price=price)
        self._db.add(entity)
        return entity