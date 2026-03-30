from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    # Отдаем сессию БД в endpoint и гарантированно закрываем ее после запроса
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()