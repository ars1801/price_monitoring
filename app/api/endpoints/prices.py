from fastapi import APIRouter, Query

from app.scrappers.service import ScraperService

router = APIRouter()
service = ScraperService()


@router.get("/")
async def get_prices(category: str | None = Query(default=None, description="Категория для контекста логов")) -> dict:
    """Тестовый endpoint: запускает live-сбор из трех источников и возвращает count по каждому."""
    payload = await service.scrape_all(category=category)

    return {
        "items": payload,
        "counts": {source: len(items) for source, items in payload.items()},
        "message": "Сбор завершен. Ошибки обрабатываются через retry и логирование.",
    }
