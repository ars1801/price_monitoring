class MagnumScraper:
    # Заготовка под парсер Magnum.
    # Пока здесь только интерфейс, реальную логику добавим позже.

    source_name = "magnum"

    async def fetch(self, url: str) -> str:
        # На следующем шаге здесь будет HTTP-запрос
        raise NotImplementedError("Логика загрузки страницы Magnum пока не реализована")

    async def parse(self, html: str) -> list[dict]:
        # На следующем шаге здесь будет парсинг HTML
        raise NotImplementedError("Логика парсинга Magnum пока не реализована")