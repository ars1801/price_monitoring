from __future__ import annotations

import logging

from app.scrappers.magnum import MAGNUM_DEFAULT_URL, MagnumScraper
from app.scrappers.small import SMALL_DEFAULT_URL, SmallScraper
from app.scrappers.spar import SPAR_DEFAULT_URL, SparScraper

logger = logging.getLogger(__name__)


class ScraperService:
    def __init__(self) -> None:
        self._scrapers = {
            "magnum": (MagnumScraper(), MAGNUM_DEFAULT_URL),
            "small": (SmallScraper(), SMALL_DEFAULT_URL),
            "spar": (SparScraper(), SPAR_DEFAULT_URL),
        }

    async def scrape_all(self, category: str | None = None) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}

        for source, (scraper, default_url) in self._scrapers.items():
            products = await scraper.scrape(url=default_url, category=category)
            logger.info(
                "Scraping finished",
                extra={"source": source, "url": default_url, "category": category, "items": len(products)},
            )
            result[source] = products

        return result