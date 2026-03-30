from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    # Базовый класс для всех ORM-моделей
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

def check_db_connection() -> bool:
    # Проверяем, что к базе можно подключиться и выполнить простой запрос
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True