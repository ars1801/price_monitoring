from typing import Any


from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.services.scrapper_service import ScrapeTarget, ScraperService

router = APIRouter()
service = ScraperService()


class ScrapeTaskDTO(BaseModel):
    source: str

    url: HttpUrl

    category: str | None = None


class BulkScrapeRequestDTO(BaseModel):
    tasks: list[ScrapeTaskDTO]



@router.get("/")
async def get_prices(
    category: str | None = Query(default=None, description="Категория для контекста логов"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload = await service.scrape_all(db=db, category=category)

    return {
        "items": payload,
        "counts": {source: item["count"] for source, item in payload.items()},
        "message": "Сбор завершен. Ошибки обрабатываются через retry и логирование.",
        "saved": {source: item["saved"] for source, item in payload.items()},
    }


@router.post("/collect")
async def collect_prices(payload: BulkScrapeRequestDTO, db: Session = Depends(get_db)) -> dict[str, Any]:
    targets = [
        ScrapeTarget(source=task.source.lower(), url=str(task.url), category=task.category)
        for task in payload.tasks
    ]
    result = await service.scrape_targets(db=db, targets=targets)
    return {
        "items": result,
        "counts": {source: item["count"] for source, item in result.items()},
        "saved": {source: item["saved"] for source, item in result.items()},
        "message": "Массовый сбор выполнен.",
    }