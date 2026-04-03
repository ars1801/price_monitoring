from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
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

@dataclass(slots=True)
class ScrapeMetrics:
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_items: int = 0
    total_saved: int = 0
    last_run_at: datetime | None = None


class ScraperService:
    def __init__(
        self,
        *,
        max_concurrency: int = 3,
        min_jitter_seconds: float = 0.05,
        max_jitter_seconds: float = 0.25,
    ) -> None:
        settings = get_settings()
        self._scrapers: dict[str, BaseScraper] = {
            "magnum": MagnumScraper(),
            "small": SmallScraper(),
            "spar": SparScraper(),
        }
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._min_jitter = min_jitter_seconds
        self._max_jitter = max_jitter_seconds
        self._snapshot_interval_minutes = settings.price_snapshot_interval_minutes
        self._metrics = ScrapeMetrics()
        self._source_metrics: dict[str, ScrapeMetrics] = {}

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
            self._record_metrics(source=target.source, successful=False, items=0, saved=0)
            return target.source, {"items": [], "count": 0, "saved": 0, "url": target.url, "category": target.category}

        try:
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
            self._record_metrics(source=target.source, successful=True, items=len(items), saved=saved)

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
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            self._record_metrics(source=target.source, successful=False, items=0, saved=0)
            logger.exception(
                "Scraping pipeline failed",
                extra={"source": target.source, "url": target.url, "category": target.category, "error": str(exc)},
            )
            return target.source, {
                "items": [],
                "count": 0,
                "saved": 0,
                "url": target.url,
                "category": target.category,
                "error": "scrape_failed",
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
        source = context.source_repo.upsert(name=source_name, base_url=source_url)
        saved = 0

        for item in products:
            name = str(item.get("name", "")).strip()
            brand_raw = item.get("brand")
            brand = str(brand_raw).strip() if isinstance(brand_raw, str) else None
            price = item.get("price")
            if not name or not isinstance(price, Decimal):
                continue

            item_source = str(item.get("source") or source_name).strip().lower()
            product = context.product_repo.upsert(name=name, brand=brand)
            product_url = self._resolve_product_url(item={**item, "source": item_source}, fallback_url=source_url)
            product_source = context.product_source_repo.upsert(
                product=product,
                source=source,
                product_url=product_url,
                category=item.get("category") or category,
            )
            inserted = context.price_history_repo.add_if_changed_or_snapshot(
                product_source=product_source,
                price=price,
                snapshot_interval_minutes=self._snapshot_interval_minutes,
            )
            if inserted:
                saved += 1

        db.commit()
        return saved
    
    def _record_metrics(self, *, source: str, successful: bool, items: int, saved: int) -> None:
        now = datetime.now(UTC)

        self._metrics.total_runs += 1
        self._metrics.total_items += items
        self._metrics.total_saved += saved
        self._metrics.last_run_at = now
        if successful:
            self._metrics.successful_runs += 1
        else:
            self._metrics.failed_runs += 1

        source_metric = self._source_metrics.setdefault(source, ScrapeMetrics())
        source_metric.total_runs += 1
        source_metric.total_items += items
        source_metric.total_saved += saved
        source_metric.last_run_at = now
        if successful:
            source_metric.successful_runs += 1
        else:
            source_metric.failed_runs += 1

    def get_metrics(self) -> dict[str, Any]:
        def serialize(metric: ScrapeMetrics) -> dict[str, Any]:
            success_rate = (
                round(metric.successful_runs / metric.total_runs, 4)
                if metric.total_runs > 0
                else 0.0
            )
            return {
                "total_runs": metric.total_runs,
                "successful_runs": metric.successful_runs,
                "failed_runs": metric.failed_runs,
                "success_rate": success_rate,
                "total_items": metric.total_items,
                "total_saved": metric.total_saved,
                "last_run_at": metric.last_run_at,
            }

        return {
            "overall": serialize(self._metrics),
            "sources": {source: serialize(metric) for source, metric in self._source_metrics.items()},
        }

    @staticmethod
    def _resolve_product_url(*, item: dict[str, Any], fallback_url: str) -> str:
        url = item.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()

        name = str(item.get("name") or "item").strip().replace(" ", "-").lower()
        source = str(item.get("source") or "source").strip().lower()
        return f"{fallback_url.rstrip('/')}/virtual/{source}/{name}"