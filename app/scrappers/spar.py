from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from app.scrappers.base import BaseScraper

SPAR_DEFAULT_URL = "https://woltasd.com/en/kaz/nur-sultan/venue/eurospar-anet-baba-44"


class SparScraper(BaseScraper):
    source_name = "spar"

    async def parse(self, *, html: str, url: str, category: str | None = None) -> list[dict[str, Any]]:
        products = self._parse_products_from_html(html=html, page_url=url, category=category)

        category_pages = self._extract_category_pages(html=html, base_url=url)
        for category_page in category_pages:
            category_html = await self.http_client.fetch_text(
                url=category_page["url"],
                source=self.source_name,
                category=category_page["category"],
            )
            if not category_html:
                continue

            category_products = self._parse_products_from_html(
                html=category_html,
                page_url=category_page["url"],
                category=category_page["category"],
            )
            products.extend(category_products)

        return self._deduplicate_products(products)

    def _parse_products_from_html(self, *, html: str, page_url: str, category: str | None = None) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []

        for payload in self._extract_json_ld(html):
            if not self._is_modal_product_payload(payload):
                continue

            price_raw = self._extract_price_from_offers(payload.get("offers")) or self._extract_price_from_offers(payload)
            price_raw = self._coerce_wolt_price(price_raw)
            if price_raw is None:
                continue
            
            product_url = self._extract_product_url(payload=payload, fallback_url=page_url)

            normalized = self._normalize_product(
                {
                    "name": payload.get("name"),
                    "brand": None,
                    "price": price_raw,
                    "source": self.source_name,
                    "url": product_url,
                    "category": category,
                }
            )
            if normalized is not None:
                products.append(normalized)

        return products
    
    def _is_modal_product_payload(self, payload: dict[str, Any]) -> bool:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            return False

        normalized_name = name.strip().lower()
        garbage_fragments = (
            "eurospar",
            "anet baba",
            "search in",
            "all items",
            "most ordered",
            "categories",
            "small kabanbay batyr №14",
            "deals",
            "most ordered",
            "new",
        )
        if any(fragment in normalized_name for fragment in garbage_fragments):
            return False

        # Оставляем только те payload, которые похожи на товарную карточку/модалку.
        has_modal_fields = any(
            key in payload
            for key in ("description", "image", "images", "id", "productId", "sku", "slug")
        )
        if not has_modal_fields:
            return False

        return self._extract_price_from_offers(payload.get("offers")) is not None or self._extract_price_from_offers(payload) is not None


    @staticmethod
    def _coerce_wolt_price(raw: Any) -> Any:
        # В ряде payload Wolt цена приходит в minor units: 11100 => 111.00
        if isinstance(raw, int) and raw >= 1000:
            return str(raw / 100)

        if isinstance(raw, str):
            text = raw.strip()
            if text.isdigit() and len(text) >= 4:
                return str(int(text) / 100)

        return raw

    def _extract_product_url(self, *, payload: dict[str, Any], fallback_url: str) -> str:
        for key in ("url", "link", "slug"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                candidate = urljoin(fallback_url, value.strip())
                if not self._looks_like_category_url(candidate):
                    return candidate

        identifier = self._extract_product_identifier(payload)
        if identifier:
            return f"{fallback_url.rstrip('/')}/product/{identifier}"

        name_slug = re.sub(r"[^a-z0-9а-яё]+", "-", str(payload.get("name") or "item").strip().lower()).strip("-")
        return f"{fallback_url.rstrip('/')}/product/{name_slug or 'item'}"

    @staticmethod
    def _looks_like_category_url(url: str) -> bool:

        return "/items/menucategory-" in url
    
    @staticmethod
    def _extract_product_identifier(payload: dict[str, Any]) -> str | None:
        for key in ("id", "productId", "sku", "@id"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip().strip("/")
            if text:
                return re.sub(r"[^a-zA-Z0-9_-]+", "-", text)
        return None

    def _extract_category_pages(self, *, html: str, base_url: str) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        seen: set[str] = set()

        for href, text in re.findall(r'<a[^>]+href="([^"]*/items/menucategory-[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
            category_url = urljoin(base_url, href.split("#")[0].strip())
            category_name = re.sub(r"<[^>]+>", "", text).strip()

            if not category_url or category_url in seen:
                continue
            seen.add(category_url)

            links.append(
                {
                    "url": category_url,
                    "category": category_name or category_url.rsplit("/", 1)[-1],
                }
            )

        return links

    @staticmethod
    def _deduplicate_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique_by_name: dict[str, dict[str, Any]] = {}

        for item in products:
            name_key = str(item.get("name", "")).strip().lower()
            if not name_key:
                continue

            existing = unique_by_name.get(name_key)
            if existing is None:
                unique_by_name[name_key] = item
                continue

            existing_price = existing.get("price")
            new_price = item.get("price")
            if new_price is not None and (existing_price is None or new_price < existing_price):
                unique_by_name[name_key] = item

        return list(unique_by_name.values())