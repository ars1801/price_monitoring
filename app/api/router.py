from fastapi import APIRouter

from app.api.endpoints.health import router as health_router
from app.api.endpoints.prices import router as prices_router

router = APIRouter()
router.include_router(health_router, tags=["Health"])
router.include_router(prices_router, prefix="/prices", tags=["Prices"])