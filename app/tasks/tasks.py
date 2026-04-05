from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.service_registry import price_alert_service, scraper_service
from app.tasks.broker import broker

logger = logging.getLogger(__name__)
settings = get_settings()

MONITORING_EVERY_HOURS = max(1, settings.monitoring_interval_hours)
MONITORING_CRON = f"0 */{MONITORING_EVERY_HOURS} * * *"


@broker.task(
    task_name="scheduled_price_monitoring",
    schedule=[{"cron": MONITORING_CRON}],
)
async def scheduled_price_monitoring(category: str | None = None) -> dict[str, Any]:
    """Периодический мониторинг цен по всем источникам."""
    db = SessionLocal()
    try:
        result = await scraper_service.scrape_all(db=db, category=category)
        total_saved = sum(item["saved"] for item in result.values())
        alert_result = await price_alert_service.notify_daily_large_changes(db=db)
        logger.info(
            "Scheduled monitoring completed",
            extra={
                "sources": list(result.keys()),
                "total_saved": total_saved,
                "alerts_detected": alert_result["detected"],
                "alerts_sent": alert_result["sent"],
                "cron": MONITORING_CRON,
            },
        )
        return {
            "cron": MONITORING_CRON,
            "sources": list(result.keys()),
            "total_saved": total_saved,
            "alerts": alert_result,
            "result": result,
        }
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Scheduled monitoring failed")
        raise
    finally:
        db.close()