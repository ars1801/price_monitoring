import logging

from app.core.config import get_settings


def setup_logging() -> None:
    # Базовая настройка логирования для всего приложения
    settings = get_settings()

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )