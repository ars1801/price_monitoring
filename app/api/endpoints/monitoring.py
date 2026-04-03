from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.price_history_repository import PriceHistoryRepository
from app.repositories.product_repository import ProductRepository
from app.services.scrapper_service import ScrapeTarget
from app.services.service_registry import scraper_service

router = APIRouter()


class ScrapeTaskDTO(BaseModel):
    source: str
    url: HttpUrl
    category: str | None = None


class MonitorRunRequestDTO(BaseModel):
    category: str | None = None
    tasks: list[ScrapeTaskDTO] | None = None


@router.post("/monitor/run")
async def run_monitoring(payload: MonitorRunRequestDTO, db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.tasks:
        targets = [
            ScrapeTarget(source=task.source.lower(), url=str(task.url), category=task.category)
            for task in payload.tasks
        ]
        result = await scraper_service.scrape_targets(db=db, targets=targets)
    else:
        result = await scraper_service.scrape_all(db=db, category=payload.category)

    return {
        "items": result,
        "counts": {source: item["count"] for source, item in result.items()},
        "saved": {source: item["saved"] for source, item in result.items()},
        "metrics": scraper_service.get_metrics(),
    }


@router.get("/products/{product_id}/prices")
async def get_product_prices(product_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    product_repo = ProductRepository(db)
    product = product_repo.get_by_id(product_id=product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    history_repo = PriceHistoryRepository(db)
    history = history_repo.get_product_price_history(product_id=product_id)

    return {
        "product": {"id": product.id, "name": product.name, "brand": product.brand},
        "history": history,
        "count": len(history),
    }


@router.get("/products/{product_id}/trend")
async def get_product_trend(
    product_id: int,
    days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    product_repo = ProductRepository(db)
    product = product_repo.get_by_id(product_id=product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    period_start = datetime.now(UTC) - timedelta(days=days)
    history_repo = PriceHistoryRepository(db)
    first_record, last_record = history_repo.get_period_bounds(
        product_id=product_id,
        period_start=period_start,
    )

    if first_record is None or last_record is None:
        return {
            "product": {"id": product.id, "name": product.name, "brand": product.brand},
            "days": days,
            "period_start": period_start,
            "message": "No price data for requested period",
            "trend": None,
        }

    start_price = Decimal(first_record.price)
    end_price = Decimal(last_record.price)
    delta = end_price - start_price
    delta_percent = round((delta / start_price) * Decimal("100"), 2) if start_price != 0 else None

    return {
        "product": {"id": product.id, "name": product.name, "brand": product.brand},
        "days": days,
        "period_start": period_start,
        "trend": {
            "start_price": start_price,
            "end_price": end_price,
            "delta": delta,
            "delta_percent": delta_percent,
            "started_at": first_record.created_at,
            "ended_at": last_record.created_at,
        },
    }