from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_db_connection
from app.services.service_registry import scraper_service

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, object]:
    # Проверяем состояние приложения и доступность базы данных
    settings = get_settings()

    db_status = False
    try:
        db_status = check_db_connection()
    except Exception:
        db_status = False

    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "debug": settings.debug,
        "database": db_status,
        "parsing_metrics": scraper_service.get_metrics(),
    }