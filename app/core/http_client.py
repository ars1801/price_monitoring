from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Комментарий про AI: список user-agent сгенерирован с помощью AI-подсказок как
# стартовый набор для снижения риска тривиальной блокировки по одному UA.
USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
)


@dataclass(slots=True)
class RetryPolicy:
    attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 3.0


class ResilientHttpClient:
    """Общий async HTTP-клиент с retry/backoff и ротацией User-Agent."""

    def __init__(
        self,
        timeout_seconds: float = 12.0,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._retry_policy = retry_policy or RetryPolicy()

    async def fetch_text(self, *, url: str, source: str, category: str | None = None) -> str | None:
        policy = self._retry_policy

        for attempt in range(1, policy.attempts + 1):
            user_agent = random.choice(USER_AGENTS)

            try:
                async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                    response = await client.get(url, headers={"User-Agent": user_agent})

                if response.status_code in {404, 502}:
                    raise httpx.HTTPStatusError(
                        f"Unexpected status code: {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()
                return response.text

            except httpx.TimeoutException:
                logger.warning(
                    "Timeout while scraping",
                    extra={
                        "source": source,
                        "url": url,
                        "category": category,
                        "attempt": attempt,
                    },
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "HTTP error while scraping",
                    extra={
                        "source": source,
                        "url": url,
                        "category": category,
                        "attempt": attempt,
                        "status_code": exc.response.status_code if exc.response else None,
                    },
                )
            except httpx.RequestError as exc:
                logger.warning(
                    "Network error while scraping",
                    extra={
                        "source": source,
                        "url": url,
                        "category": category,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )

            if attempt < policy.attempts:
                exponential = policy.base_delay_seconds * (2 ** (attempt - 1))
                jitter = random.uniform(0.0, 0.3)
                await asyncio.sleep(min(exponential + jitter, policy.max_delay_seconds))

        logger.error(
            "Scraping failed after retries",
            extra={"source": source, "url": url, "category": category},
        )
        return None
