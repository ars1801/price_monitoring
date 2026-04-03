from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.price_history_repository import PriceHistoryRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_source_repository import ProductSourceRepository
from app.repositories.source_repository import SourceRepository
from app.scrappers.base import BaseScraper
from app.scrappers.magnum import MAGNUM_DEFAULT_URL, MagnumScraper
from app.scrappers.small import SMALL_DEFAULT_URL, SmallScraper
from app.scrappers.spar import SPAR_DEFAULT_URL, SparScraper

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ScrapeTarget:
    source: str
    url: str
    category: str | None = None


@dataclass(slots=True)
class SaveContext:
    source_repo: SourceRepository
    product_repo: ProductRepository
    product_source_repo: ProductSourceRepository
    price_history_repo: PriceHistoryRepository


class ScraperService:
    def __init__(
        self,
        *,
        max_concurrency: int = 3,
        min_jitter_seconds: float = 0.05,
        max_jitter_seconds: float = 0.25,
    ) -> None:
        self._scrapers: dict[str, BaseScraper] = {
            "magnum": MagnumScraper(),
            "small": SmallScraper(),
            "spar": SparScraper(),
        }
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._min_jitter = min_jitter_seconds
        self._max_jitter = max_jitter_seconds

    async def scrape_all(self, db: Session, category: str | None = None) -> dict[str, dict[str, Any]]:
        targets = [
            ScrapeTarget(source="magnum", url=MAGNUM_DEFAULT_URL, category=category),
            ScrapeTarget(source="small", url=SMALL_DEFAULT_URL, category=category),
            ScrapeTarget(source="spar", url=SPAR_DEFAULT_URL, category=category),
        ]
        return await self.scrape_targets(db=db, targets=targets)

    async def scrape_targets(self, *, db: Session, targets: list[ScrapeTarget]) -> dict[str, dict[str, Any]]:
        context = SaveContext(
            source_repo=SourceRepository(db),
            product_repo=ProductRepository(db),
            product_source_repo=ProductSourceRepository(db),
            price_history_repo=PriceHistoryRepository(db),
        )
        tasks = [self._run_target(db=db, target=target, context=context) for target in targets]
        pairs = await asyncio.gather(*tasks)
        return {source: payload for source, payload in pairs}

    async def _run_target(
        self,
        *,
        db: Session,
        target: ScrapeTarget,
        context: SaveContext,
    ) -> tuple[str, dict[str, Any]]:
        scraper = self._scrapers.get(target.source)
        if scraper is None:
            logger.warning("Unknown source requested", extra={"source": target.source, "url": target.url})
            return target.source, {"items": [], "count": 0, "saved": 0, "url": target.url, "category": target.category}

        async with self._semaphore:
            await asyncio.sleep(random.uniform(self._min_jitter, self._max_jitter))
            items = await scraper.scrape(url=target.url, category=target.category)

        saved = self._save_products(
            db=db,
            context=context,
            source_name=target.source,
            source_url=target.url,
            category=target.category,
            products=items,
        )

        logger.info(
            "Scraping finished",
            extra={
                "source": target.source,
                "url": target.url,
                "category": target.category,
                "items": len(items),
                "saved": saved,
            },
        )
        return target.source, {
            "items": items,
            "count": len(items),
            "saved": saved,
            "url": target.url,
            "category": target.category,
        }

    def _save_products(
        self,
        *,
        db: Session,
        context: SaveContext,
        source_name: str,
        source_url: str,
        category: str | None,
        products: list[dict[str, Any]],
    ) -> int:
        source = context.source_repo.get_or_create(name=source_name, base_url=source_url)
        saved = 0

        for item in products:
            name = str(item.get("name", "")).strip()
            brand_raw = item.get("brand")
            brand = str(brand_raw).strip() if isinstance(brand_raw, str) else None
            price = item.get("price")
            if not name or not isinstance(price, Decimal):
                continue

            item_source = str(item.get("source") or source_name).strip().lower()
            product = context.product_repo.get_or_create(name=name, brand=brand)
            product_url = self._resolve_product_url(item={**item, "source": item_source}, fallback_url=source_url)
            product_source = context.product_source_repo.get_or_create(
                product=product,
                source=source,
                product_url=product_url,
                category=item.get("category") or category,
            )
            context.price_history_repo.add(product_source=product_source, price=price)
            saved += 1

        db.commit()
        return saved

    @staticmethod
    def _resolve_product_url(*, item: dict[str, Any], fallback_url: str) -> str:
        url = item.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()

        name = str(item.get("name") or "item").strip().replace(" ", "-").lower()
        source = str(item.get("source") or "source").strip().lower()
        return f"{fallback_url.rstrip('/')}/virtual/{source}/{name}"