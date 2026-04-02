from __future__ import annotations

import json
import logging
import re
import os
from abc import ABC, abstractmethod
from typing import Any

from pydantic import ValidationError

from app.core.http_client import ResilientHttpClient
from app.scrappers.dto import CleanProductDTO, RawProductDTO

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    source_name: str

    def __init__(self, http_client: ResilientHttpClient | None = None) -> None:
        self.http_client = http_client or ResilientHttpClient()

    async def scrape(self, *, url: str, category: str | None = None) -> list[dict[str, Any]]:
        html = await self.http_client.fetch_text(url=url, source=self.source_name, category=category)
        if not html:
            return []

        try:
            return await self.parse(html=html, url=url, category=category)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Parser error",
                extra={
                    "source": self.source_name,
                    "url": url,
                    "category": category,
                    "error": str(exc),
                },
            )
            return []

    @abstractmethod
    async def parse(self, *, html: str, url: str, category: str | None = None) -> list[dict[str, Any]]:
        """Должен вернуть список товаров в едином формате."""


    def _debug_print(self, message: str, **context: Any) -> None:
        if os.getenv("SCRAPER_DEBUG", "1") != "1":
            return
        details = " ".join(f"{key}={value}" for key, value in context.items())
        print(f"[SCRAPER_DEBUG] source={self.source_name} {message} {details}".strip(), flush=True)

    def _extract_json_ld(self, html: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        for match in matches:
            try:
                payload = json.loads(match.strip())
            except json.JSONDecodeError:
                continue

            items.extend(self._flatten_json_ld(payload))

        embedded_items = self._extract_embedded_json_objects(html)
        if embedded_items:
            items.extend(embedded_items)

        self._debug_print(
            "json_ld_extracted",
            script_tags=len(matches),
            flattened_items=len(items),
            embedded_items=len(embedded_items),
        )
        return items
    
    def _extract_embedded_json_objects(self, html: str) -> list[dict[str, Any]]:
        """Фолбэк для SPA-страниц, где товары лежат в inline-state, а не в ld+json."""
        items: list[dict[str, Any]] = []

        script_contents = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
        for script_content in script_contents:
            script = script_content.strip()
            if not script:
                continue

            if script.startswith("{") or script.startswith("["):
                try:
                    payload = json.loads(script)
                except json.JSONDecodeError:
                    continue
                items.extend(self._flatten_json_ld(payload))
                continue

            for pattern in (
                r"__NEXT_DATA__\s*=\s*({.*?})\s*;",
                r"__PRELOADED_STATE__\s*=\s*({.*?})\s*;",
                r"__INITIAL_STATE__\s*=\s*({.*?})\s*;",
                r"__NUXT__\s*=\s*({.*?})\s*;",
            ):
                for match in re.findall(pattern, script, re.DOTALL):
                    try:
                        payload = json.loads(match)
                    except json.JSONDecodeError:
                        continue
                    items.extend(self._flatten_json_ld(payload))

        return items

    def _flatten_json_ld(self, payload: Any) -> list[dict[str, Any]]:
        """Рекурсивно разворачивает все вложенные dict/list узлы в единый список dict."""
        if isinstance(payload, dict):
            items = [payload]
            for value in payload.values():
                if isinstance(value, (dict, list)):
                    items.extend(self._flatten_json_ld(value))
            return items

        if isinstance(payload, list):
            items: list[dict[str, Any]] = []
            for obj in payload:
                if isinstance(obj, (dict, list)):
                    items.extend(self._flatten_json_ld(obj))
            return items

        return []

    def _is_product_payload(self, payload: dict[str, Any]) -> bool:
        payload_type = payload.get("@type")
        if isinstance(payload_type, str) and "Product" in payload_type:
            return True
        if isinstance(payload_type, list) and any(isinstance(item, str) and "Product" in item for item in payload_type):
            return True

        # Фолбэк: на некоторых SPA товар не помечен @type, но содержит name + цену.
        has_name = isinstance(payload.get("name"), str) and bool(payload.get("name").strip())
        has_price = self._extract_price_from_offers(payload.get("offers")) is not None or self._extract_price_from_offers(payload) is not None
        return has_name and has_price

    def _is_non_product_name(self, name: Any) -> bool:
        if not isinstance(name, str):
            return True

        normalized = name.strip().lower()
        if not normalized:
            return True

        generic_sections = {
            "deals",
            "most ordered",
            "new",
            "popular",
            "categories",
            "best sellers",
        }
        if normalized in generic_sections:
            return True

        return normalized.startswith(self.source_name.lower()) and "№" in normalized

    def _extract_brand(self, payload: dict[str, Any]) -> str:
        for key in ("brand", "manufacturer"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                brand_name = candidate.get("name")
                if isinstance(brand_name, str) and brand_name.strip():
                    return brand_name.strip()
            elif isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        # AI-note: подставляем source как fallback для brand, чтобы не терять
        # товары без бренда в JSON-LD, сохраняя обязательность поля в Clean DTO.
        return self.source_name

    def _extract_price_from_offers(self, offers: Any) -> Any:
        if isinstance(offers, dict):
            for key in ("price", "finalPrice", "currentPrice", "discountedPrice", "amount", "value"):
                value = offers.get(key)
                if isinstance(value, dict):
                    nested = self._extract_price_from_offers(value)
                    if nested is not None:
                        return nested
                elif value is not None:
                    return value

            price_spec = offers.get("priceSpecification")
            if isinstance(price_spec, dict):
                for key in ("price", "minPrice", "maxPrice"):
                    if price_spec.get(key) is not None:
                        return price_spec.get(key)

            for key in ("lowPrice", "highPrice"):
                if offers.get(key) is not None:
                    return offers.get(key)

            for value in offers.values():
                if isinstance(value, (dict, list)):
                    extracted = self._extract_price_from_offers(value)
                    if extracted is not None:
                        return extracted

        if isinstance(offers, list):
            for offer in offers:
                extracted = self._extract_price_from_offers(offer)
                if extracted is not None:
                    return extracted

        return None

    def _normalize_product(self, raw_product: dict[str, Any]) -> dict[str, Any] | None:
        """Приводит сырой объект товара к валидному контракту или возвращает None."""
        try:
            raw_dto = RawProductDTO.model_validate(raw_product)
            # AI-note: используем двухшаговый DTO (raw -> clean), чтобы отделить
            # нестабильный формат сайтов от строгого контракта сервиса и упростить отладку.
            clean_dto = CleanProductDTO.model_validate(raw_dto.model_dump())
        except ValidationError as exc:
            errors = exc.errors()
            logger.debug(
                "Invalid product payload",
                extra={"source": self.source_name, "errors": errors, "payload": raw_product},
            )
            self._debug_print(
                "normalize_failed",
                errors=errors,
                name=raw_product.get("name"),
                brand=raw_product.get("brand"),
                price=raw_product.get("price"),
            )
            return None

        return clean_dto.model_dump(mode="python")