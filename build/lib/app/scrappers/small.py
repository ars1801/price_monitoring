class SmallScraper:
    # Заготовка под парсер Small

    source_name = "small"

    async def fetch(self, url: str) -> str:
        raise NotImplementedError("Логика загрузки страницы Small пока не реализована")

    async def parse(self, html: str) -> list[dict]:
        raise NotImplementedError("Логика парсинга Small пока не реализована")