# price_monitoring_system

## Рекомендуемый план следующих коммитов

Ниже — последовательность коммитов, которая закрывает требования тестового задания от архитектуры до инфраструктуры.

1. **feat(scraper): единый scraping core + стратегии магазинов**
   - Вынести общий асинхронный клиент (`httpx.AsyncClient`) и интерфейс стратегии (`BaseScraper`).
   - Для `Magnum/Small/SPAR` оставить отдельные адаптеры парсинга.
   - Добавить ротацию User-Agent и базовый retry/backoff для `404/502/Timeout`.
   - Добавить нормальное логирование ошибок парсинга (с контекстом URL/category), чтобы сервис не падал.

2. **feat(validation): pydantic-схемы входа/выхода + нормализация Decimal**
   - Добавить DTO-модели для сырых данных и очищенных данных.
   - Валидировать обязательные поля (`name`, `brand`, `price`, `source`).
   - Приводить цены к `Decimal` в едином формате с защитой от мусорных значений (`"-"`, `"N/A"`, пусто).
   - Добавить комментарии в коде, где использованы AI-подсказки и почему выбран конкретный подход.

3. **feat(service): orchestration use-case для массового сбора**
   - Отдельный application-сервис для запуска сбора по списку URL/категорий.
   - Настроить ограничение частоты запросов (rate limiting, например, через `asyncio.Semaphore` + sleep jitter).
   - Сохранение через единый слой репозиториев, без прямого доступа к БД из scraper-слоя.

4. **feat(db): корректное ведение истории цен и дедупликация снимков**
   - Реализовать логику upsert для `product/source/product_source`.
   - В `price_history` писать новую запись только при изменении цены или по расписанию snapshot.
   - Добавить индексы на `product_source_id`, `created_at` для быстрых запросов динамики.
   - Подготовить и применить Alembic-миграцию под новые индексы/ограничения.

5. **feat(api): endpoints для мониторинга и аналитики**
   - `POST /monitor/run` — запустить сбор.
   - `GET /products/{id}/prices` — история цен по товару.
   - `GET /products/{id}/trend?days=...` — изменение за период.
   - `GET /health` и метрики ошибок/успехов парсинга.

6. **feat(tasks): фоновое расписание (Taskiq) для регулярного мониторинга**
   - Настроить брокер и периодические задачи (например, каждые N часов).
   - Разделить API-процессы и worker-процессы в docker-compose.

7. **feat(notify): Telegram-уведомления при изменении >10% за сутки (bonus)**
   - Сервис расчета процента изменения цены за 24 часа.
   - Отправка уведомления через Telegram Bot API.
   - Конфигурация токена/чата через env.

8. **test: покрытие критической бизнес-логики и валидации**
   - Unit-тесты для парсеров (на фикстурах HTML).
   - Unit-тесты для валидаторов Pydantic и нормализации Decimal.
   - Integration-тесты репозиториев и API.

9. **chore(infra): production-like docker-compose up одной командой**
   - Поднять `api + worker + postgres + (опционально) redis/rabbit`.
   - Healthcheck для контейнеров.
   - Команда инициализации миграций при старте (или отдельный migration job).

10. **docs: полноценный README под критерии оценки**
    - Как запустить локально и в Docker.
    - Как добавить 4-й, 10-й, 100-й супермаркет (масштабирование через новые стратегии).
    - Описание архитектуры (layers: scraper/domain/repository/api/tasks).
    - Обоснование trade-offs и антихрупкости при изменении верстки магазинов.

## Пример формата коммитов

- `feat(scraper): add base strategy and resilient http client`
- `feat(validation): add pydantic contracts and decimal normalizer`
- `feat(tasks): schedule periodic monitoring with taskiq`
- `feat(notify): add telegram alerts for >10% daily price change`
- `docs(readme): document runbook and scaling to 100+ stores`

