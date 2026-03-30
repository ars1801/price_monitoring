from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_prices() -> dict:
    # Временный endpoint-заглушка.
    # На следующих шагах здесь будет получение цен из БД.
    return {
        "items": [],
        "message": "Список цен пока пуст. Логика будет добавлена в следующих коммитах.",
    }