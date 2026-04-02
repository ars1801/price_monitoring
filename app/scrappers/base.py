from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from app.core.http_client import ResilientHttpClient

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

    def _extract_json_ld(self, html: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for match in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                payload = json.loads(match.strip())
            except json.JSONDecodeError:
                continue

            if isinstance(payload, dict):
                items.append(payload)
            elif isinstance(payload, list):
                items.extend(obj for obj in payload if isinstance(obj, dict))
        return items