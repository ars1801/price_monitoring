from __future__ import annotations

from datetime import UTC, datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import PriceHistory, Product, ProductSource, Source


@dataclass(slots=True)
class PersistResult:
    saved: int = 0


class ScrapeRepository:
    """Единый слой сохранения результатов скрапинга в БД."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._snapshot_interval_minutes = get_settings().price_snapshot_interval_minutes

    def save_products(
        self,
        *,
        source_name: str,
        source_url: str,
        category: str | None,
        products: list[dict[str, Any]],
    ) -> PersistResult:
        source = self._get_or_create_source(name=source_name, base_url=source_url)
        saved = 0

        for item in products:
            name = str(item.get("name", "")).strip()
            brand_raw = item.get("brand")
            brand = str(brand_raw).strip() if isinstance(brand_raw, str) else None
            price = item.get("price")
            if not name or not isinstance(price, Decimal):
                continue

            product = self._get_or_create_product(name=name, brand=brand)
            product_url = self._resolve_product_url(item=item, fallback_url=source_url)
            product_source = self._get_or_create_product_source(
                product=product,
                source=source,
                product_url=product_url,
                category=item.get("category") or category,
            )

            if self._add_price_if_changed_or_snapshot(product_source=product_source, price=price):
                saved += 1

        self._db.commit()
        return PersistResult(saved=saved)

    def _get_or_create_source(self, *, name: str, base_url: str) -> Source:
        source = self._db.scalar(select(Source).where(Source.name == name))
        if source:
            if base_url and source.base_url != base_url:
                source.base_url = base_url
            return source

        source = Source(name=name, base_url=base_url)
        self._db.add(source)
        self._db.flush()
        return source

    def _get_or_create_product(self, *, name: str, brand: str | None) -> Product:
        # Требование: одинаковые названия не должны плодить новые Product.
        product = self._db.scalar(select(Product).where(Product.name == name))
        if product:
            if brand and product.brand != brand:
                product.brand = brand
            return product

        product = Product(name=name, brand=brand)
        self._db.add(product)
        self._db.flush()
        return product

    def _get_or_create_product_source(
        self,
        *,
        product: Product,
        source: Source,
        product_url: str,
        category: str | None,
    ) -> ProductSource:
        product_source = self._db.scalar(
            select(ProductSource).where(
                ProductSource.source_id == source.id,
                ProductSource.product_url == product_url,
            )
        )
        if product_source:
            if product_source.product_id != product.id:
                product_source.product = product
            if category and product_source.category != category:
                product_source.category = category
            if not product_source.is_active:
                product_source.is_active = True
            return product_source

        product_source = ProductSource(
            product=product,
            source=source,
            product_url=product_url,
            category=category,
            is_active=True,
        )
        self._db.add(product_source)
        self._db.flush()
        return product_source

    @staticmethod
    def _resolve_product_url(*, item: dict[str, Any], fallback_url: str) -> str:
        url = item.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()

        name = str(item.get("name") or "item").strip().replace(" ", "-").lower()
        source = str(item.get("source") or "source").strip().lower()
        return f"{fallback_url.rstrip('/')}/virtual/{source}/{name}"

    def _add_price_if_changed_or_snapshot(self, *, product_source: ProductSource, price: Decimal) -> bool:
        last_record = self._db.scalar(
            select(PriceHistory)
            .where(PriceHistory.product_source_id == product_source.id)
            .order_by(PriceHistory.created_at.desc(), PriceHistory.id.desc())
            .limit(1)
        )
        if last_record is None or last_record.price != price:
            self._db.add(PriceHistory(product_source=product_source, price=price))
            return True

        if self._snapshot_interval_minutes <= 0:
            return False

        created_at = last_record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - created_at >= timedelta(minutes=self._snapshot_interval_minutes):
            self._db.add(PriceHistory(product_source=product_source, price=price))
            return True

        return False