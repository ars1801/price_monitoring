from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.price_history_repository import PriceChangeCandidate, PriceHistoryRepository
from app.services.telegram_notifier import TelegramNotifier


class PriceAlertService:
    def __init__(self, *, settings: Settings, notifier: TelegramNotifier) -> None:
        self._settings = settings
        self._notifier = notifier

    async def notify_daily_large_changes(self, *, db: Session) -> dict[str, int]:
        threshold = Decimal(str(self._settings.price_change_alert_threshold_percent))
        now = datetime.now(UTC)
        period_start = now - timedelta(hours=24)
        latest_after = now - timedelta(hours=max(1, self._settings.monitoring_interval_hours))

        history_repo = PriceHistoryRepository(db)
        changes = history_repo.get_significant_product_source_changes(
            period_start=period_start,
            min_abs_change_percent=abs(threshold),
            latest_after=latest_after,
        )

        sent = 0
        for change in changes:
            text = self._format_message(change=change, threshold=abs(threshold))
            ok = await self._notifier.send_message(text)
            if ok:
                sent += 1

        return {"detected": len(changes), "sent": sent}

    @staticmethod
    def _format_message(*, change: PriceChangeCandidate, threshold: Decimal) -> str:
        trend = "📈" if change.delta_percent > 0 else "📉"
        sign = "+" if change.delta_percent > 0 else ""
        brand = f" ({change.product_brand})" if change.product_brand else ""

        return (
            f"{trend} Изменение цены >{threshold.quantize(Decimal('0.01'))}% за 24ч\n"
            f"Товар: {change.product_name}{brand}\n"
            f"Источник: {change.source_name}\n"
            f"Было: {change.start_price}\n"
            f"Стало: {change.end_price}\n"
            f"Изменение: {sign}{change.delta_percent.quantize(Decimal('0.01'))}%\n"
            f"Период: {change.started_at.isoformat()} — {change.ended_at.isoformat()}\n"
            f"Ссылка: {change.product_url}"
        )