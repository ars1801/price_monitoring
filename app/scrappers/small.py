from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

from app.scrappers.base import BaseScraper

logger = logging.getLogger(__name__)

SMALL_DEFAULT_URL = "https://wolt.com/en/kaz/nur-sultan/venue/small-ast14"


class SmallScraper(BaseScraper):
    source_name = "small"

    async def parse(self, *, html: str, url: str, category: str | None = None) -> list[dict[str, Any]]:
        products = self._parse_products_from_html(
            html=html,
            page_url=url,
            category=category,
        )

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

    def _parse_products_from_html(
        self,
        *,
        html: str,
        page_url: str,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []

        for payload in self._extract_json_ld(html):
            if not isinstance(payload, dict):
                continue

            if not self._is_modal_product_payload(payload):
                continue

            price_raw = self._extract_price_from_payload(payload)
            price_raw = self._coerce_wolt_price(price_raw)

            if not self._is_valid_price_value(price_raw):
                continue

            product_url = self._extract_product_url(payload=payload, fallback_url=page_url)

            normalized = self._normalize_product(
                {
                    "name": payload.get("name"),
                    "brand": self._extract_brand(payload),
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
            "search in",
            "all items",
            "most ordered",
            "categories",
            "deals",
            "shop by category",
            "small kabanbay batyr",
            "eurospar",
            "anet baba",
        )
        if any(fragment in normalized_name for fragment in garbage_fragments):
            return False

        if normalized_name in {"new", "sale", "popular"}:
            return False

        slug = payload.get("slug")
        if isinstance(slug, str) and slug.startswith("menucategory-"):
            return False

        identifier = payload.get("id") or payload.get("productId") or payload.get("sku") or payload.get("@id")
        if identifier is None:
            return False

        image_like = payload.get("image") or payload.get("images") or payload.get("thumbnail")
        description_like = payload.get("description") or payload.get("shortDescription")
        price_like = self._extract_price_from_payload(payload)

        return bool(image_like or description_like or price_like is not None)

    def _extract_price_from_payload(self, payload: dict[str, Any]) -> Any:
        direct_candidates = (
            "price",
            "salePrice",
            "currentPrice",
            "finalPrice",
            "basePrice",
            "unitPrice",
            "displayPrice",
            "amount",
            "value",
            "minPrice",
            "maxPrice",
        )

        for key in direct_candidates:
            value = payload.get(key)
            if value is not None:
                return value

        nested_candidates = (
            "pricing",
            "priceRange",
            "priceInfo",
            "productVariants",
            "variants",
            "defaultVariant",
            "purchaseOptions",
            "commerce",
            "commercial",
            "item",
        )

        for key in nested_candidates:
            value = payload.get(key)
            found = self._deep_find_price(value)
            if found is not None:
                return found

        return self._deep_find_price(payload)

    def _deep_find_price(self, value: Any) -> Any:
        price_keys = (
            "price",
            "salePrice",
            "currentPrice",
            "finalPrice",
            "basePrice",
            "unitPrice",
            "displayPrice",
            "amount",
            "value",
            "minorUnits",
            "priceAmount",
        )

        if isinstance(value, dict):
            for key in price_keys:
                candidate = value.get(key)
                if candidate is not None and self._looks_like_price(candidate):
                    return candidate

            for nested in value.values():
                found = self._deep_find_price(nested)
                if found is not None:
                    return found

        elif isinstance(value, list):
            for item in value:
                found = self._deep_find_price(item)
                if found is not None:
                    return found

        return None

    @staticmethod
    def _looks_like_price(value: Any) -> bool:
        if isinstance(value, (int, float)):
            return value > 0

        if isinstance(value, str):
            text = value.strip().replace(" ", "").replace(",", ".")
            return bool(re.fullmatch(r"\d+(\.\d{1,2})?", text))

        return False

    @staticmethod
    def _is_valid_price_value(value: Any) -> bool:
        if isinstance(value, (int, float)):
            return value > 0

        if isinstance(value, str):
            text = value.strip().replace(" ", "").replace(",", ".")
            return bool(re.fullmatch(r"\d+(\.\d{1,2})?", text))

        return False

    @staticmethod
    def _coerce_wolt_price(raw: Any) -> Any:
        if isinstance(raw, int):
            if raw <= 0:
                return None
            if raw >= 1000:
                return str(raw / 100)
            return str(raw)

        if isinstance(raw, float):
            if raw <= 0:
                return None
            return str(raw)

        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return None

            normalized = text.replace("₸", "").replace(" ", "").replace(",", ".")
            if normalized.isdigit() and len(normalized) >= 4:
                return str(int(normalized) / 100)

            if re.fullmatch(r"\d+(\.\d{1,2})?", normalized):
                return normalized

        return raw

    def _extract_product_url(self, *, payload: dict[str, Any], fallback_url: str) -> str:
        for key in ("url", "link", "canonicalUrl"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                candidate = urljoin(fallback_url, value.strip())
                if not self._looks_like_category_url(candidate):
                    return candidate

        slug = payload.get("slug")
        if isinstance(slug, str) and slug.strip() and not slug.startswith("menucategory-"):
            return f"{fallback_url.rstrip('/')}/product/{slug.strip('/')}"

        identifier = self._extract_product_identifier(payload)
        if identifier:
            return f"{fallback_url.rstrip('/')}/product/{identifier}"

        name_slug = re.sub(r"[^a-z0-9а-яё]+", "-", str(payload.get('name') or 'item').strip().lower()).strip("-")
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

    @staticmethod
    def _extract_brand(payload: dict[str, Any]) -> str | None:
        brand = payload.get("brand")
        if isinstance(brand, str) and brand.strip():
            return brand.strip()

        if isinstance(brand, dict):
            name = brand.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()

        manufacturer = payload.get("manufacturer")
        if isinstance(manufacturer, str) and manufacturer.strip():
            return manufacturer.strip()

        return None

    def _extract_category_pages(self, *, html: str, base_url: str) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        seen: set[str] = set()

        for href, text in re.findall(
            r'<a[^>]+href="([^"]*/items/menucategory-[^"]+)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        ):
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