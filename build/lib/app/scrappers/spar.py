class SparScraper:
    # Заготовка под парсер SPAR

    source_name = "spar"

    async def fetch(self, url: str) -> str:
        raise NotImplementedError("Логика загрузки страницы SPAR пока не реализована")

    async def parse(self, html: str) -> list[dict]:
        raise NotImplementedError("Логика парсинга SPAR пока не реализована")