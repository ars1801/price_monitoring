from __future__ import annotations

import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._enabled = settings.telegram_enabled
        self._api_base_url = settings.telegram_api_base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self._enabled and self._token and self._chat_id)

    async def send_message(self, message: str) -> bool:
        if not self.is_configured:
            logger.info("Telegram notifier skipped: not configured")
            return False

        url = f"{self._api_base_url}/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
            if not body.get("ok", False):
                logger.error("Telegram API returned non-ok response", extra={"response": body})
                return False
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Telegram message send failed", extra={"error": str(exc)})
            return False