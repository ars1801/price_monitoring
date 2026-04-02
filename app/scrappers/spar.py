from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.scrappers.base import BaseScraper

SPAR_DEFAULT_URL = "https://eda.yandex.kz/ru-kz/ru-kz/ru-kz/retail/spar_novyj_brend/catalog/290456?placeSlug=spar_novyj_brend_test_&relatedBrandSlug=spar_novyj_brend"


class SparScraper(BaseScraper):
    source_name = "spar"

    async def parse(self, *, html: str, url: str, category: str | None = None) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []

        for payload in self._extract_json_ld(html):
            if payload.get("@type") != "Product":
                continue

            offers = payload.get("offers") or {}
            price_raw = offers.get("price") if isinstance(offers, dict) else None
            price = self._to_decimal(price_raw)
            if price is None:
                continue

            products.append(
                {
                    "name": payload.get("name"),
                    "brand": self._extract_brand(payload),
                    "price": price,
                    "source": self.source_name,
                    "url": url,
                    "category": category,
                }
            )

        return products

    @staticmethod
    def _extract_brand(payload: dict[str, Any]) -> str | None:
        brand = payload.get("brand")
        if isinstance(brand, dict):
            return brand.get("name")
        if isinstance(brand, str):
            return brand
        return None

    @staticmethod
    def _to_decimal(raw: Any) -> Decimal | None:
        if raw is None:
            return None
        try:
            return Decimal(str(raw).replace(",", ".").strip())
        except (InvalidOperation, ValueError):
            return None
