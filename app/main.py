from fastapi import FastAPI

from app.api.router import router
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.include_router(router, prefix=settings.api_prefix)