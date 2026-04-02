from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.scrappers.base import BaseScraper

SMALL_DEFAULT_URL = "https://wolt.com/en/kaz/nur-sultan/venue/small-ast14"


class SmallScraper(BaseScraper):
    source_name = "small"

    async def parse(self, *, html: str, url: str, category: str | None = None) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        total_payloads = 0
        product_payloads = 0

        for payload in self._extract_json_ld(html):
            total_payloads += 1
            if not self._is_product_payload(payload):
                if total_payloads <= 3:
                    self._debug_print("payload_skipped", keys=list(payload.keys())[:8], has_name=bool(payload.get("name")), price_guess=self._extract_price_from_offers(payload.get("offers")) or self._extract_price_from_offers(payload))
                continue

            product_payloads += 1
            price_raw = self._extract_price_from_offers(payload.get("offers")) or self._extract_price_from_offers(payload)
            if price_raw is None:
                if total_payloads <= 3:
                    self._debug_print("product_without_price", name=payload.get("name"), keys=list(payload.keys())[:8])
                continue

            normalized = self._normalize_product(
                {
                    "name": payload.get("name"),
                    "brand": self._extract_brand(payload) or self.source_name,
                    "price": price_raw,
                    "source": self.source_name,
                    "url": url,
                    "category": category,
                }
            )
            if normalized is not None:
                products.append(normalized)

        self._debug_print("parse_summary", total_payloads=total_payloads, product_payloads=product_payloads, normalized_items=len(products), url=url, category=category)
        return products

    @staticmethod
    def _extract_brand(payload: dict[str, Any]) -> str | None:
        brand = payload.get("brand")
        if isinstance(brand, dict):
            return brand.get("name")
        if isinstance(brand, str):
            return brand
        return None