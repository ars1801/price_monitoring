# Price Monitoring System (Astana)

Прототип backend-системы мониторинга цен для крупнейших торговых сетей Астаны: **Magnum(В текущей версии нет возомжности подключить)**, **Small**, **SPAR**.

Проект ориентирован не только на сбор данных, но и на:
- архитектурную устойчивость;
- строгую валидацию данных;
- хранение истории изменения цен;
- запуск всей инфраструктуры одной командой через Docker Compose.

---

## 1) Что реализовано

### Функциональность мониторинга
- Асинхронный сбор данных из источников (скрейперы по каждому магазину).
- Входные сценарии:
  - сбор по дефолтным источникам;
  - сбор по переданному списку `tasks` с `source + url + category`.
- Устойчивость сети:
  - ротация `User-Agent`;
  - retry + exponential backoff + jitter;
  - обработка `404`, `502`, `Timeout`, `RequestError` с логированием.

### Валидация и нормализация
- Все сырые товары проходят двухэтапную Pydantic-валидацию (`RawProductDTO -> CleanProductDTO`).
- Обязательные поля (`name`, `source`) валидируются.
- Цена приводится к единому `Decimal(10, 2)` и очищается от мусорных значений.

### Хранение данных
- PostgreSQL + SQLAlchemy.
- Модели:
  - `products` — справочник товаров;
  - `sources` — источники;
  - `product_sources` — связка товара с конкретным магазином/карточкой;
  - `price_history` — временной ряд цен.
- История цены сохраняется при:
  - изменении цены;
  - или наступлении snapshot-интервала (даже без изменения).

### Фоновая обработка
- Taskiq + Redis:
  - плановый мониторинг цен;
  - ежедневная проверка существенных изменений цены и отправка Telegram-уведомлений.

---

## 2) Архитектура (Clean-ish)

```text
app/
  api/            # REST endpoints (входной слой)
  scrappers/      # Интеграция с внешними сайтами и парсинг
  services/       # Бизнес-логика (оркестрация мониторинга, алерты)
  repositories/   # Работа с БД (query/update слой)
  models/         # ORM-модели
  core/           # Конфиг, логирование, HTTP-клиент, DB setup
  tasks/          # Фоновые задачи и расписание (Taskiq)
```

Принцип разделения:
- **Parsing layer**: извлечение и нормализация сырого контента.
- **Business layer**: правила сохранения, метрики, логика алертов.
- **Persistence layer**: атомарная работа с сущностями БД.

---

## 3) Быстрый запуск

### Требования
- Docker + Docker Compose.

### Запуск всего проекта
```bash
docker-compose up --build
```

После старта:
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

### Что поднимается в compose
- `db` (PostgreSQL)
- `redis`
- `migrate` (Alembic `upgrade head`)
- `api` (FastAPI + Uvicorn)
- `worker` (Taskiq worker)
- `scheduler` (Taskiq scheduler)

---

## 4) Миграции

### Применить миграции вручную
```bash
alembic upgrade head
```

### Создать новую миграцию
```bash
alembic revision --autogenerate -m "your message"
alembic upgrade head
```

---

## 5) Основные API endpoints

- `GET /api/health` — healthcheck.
- `GET /api/prices` — сбор по дефолтным источникам.
- `POST /api/prices/collect` — массовый запуск скрейпа по списку задач.
- `POST /api/monitor/run` — запуск мониторинга (с optional `tasks`).
- `GET /api/monitor/products/{product_id}/prices` — история цен товара.
- `GET /api/monitor/products/{product_id}/trend?days=7` — динамика цены.

Пример тела `POST /api/monitor/run`:
```json
{
  "tasks": [
    {
      "source": "small",
      "url": "https://wolt.com/en/kaz/nur-sultan/venue/small-ast14",
      "category": "Молоко"
    },
    {
      "source": "spar",
      "url": "https://wolt.com/en/kaz/nur-sultan/venue/eurospar-anet-baba-44",
      "category": "Хлеб"
    }
  ]
}
```

---

## 6) Telegram-уведомления (>10% за сутки)

В проекте есть фоновая задача, которая раз в сутки:
1. находит товары с изменением цены выше порога (`PRICE_CHANGE_ALERT_THRESHOLD_PERCENT`, по умолчанию 10%),
2. отправляет уведомления в Telegram.

### Настройки окружения
- `TELEGRAM_ENABLED=true|false`
- `TELEGRAM_BOT_TOKEN=...`
- `TELEGRAM_CHAT_ID=...`
- `TELEGRAM_API_BASE_URL=https://api.telegram.org`
- `PRICE_CHANGE_ALERT_THRESHOLD_PERCENT=10`

Если Telegram не настроен, отправка пропускается с логированием.

---

## 7) Конфигурация (основные env)

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_URL`
- `MONITORING_INTERVAL_HOURS`
- `PRICE_SNAPSHOT_INTERVAL_MINUTES`
- `PRICE_CHANGE_ALERT_THRESHOLD_PERCENT`
- `LOG_LEVEL`

---

## 8) Масштабирование на 100+ супермаркетов

Рекомендуемая стратегия:

1. **Реестр источников**
   - вынести список источников/категорий/URL в БД (а не в код);
   - добавить флаг активности и приоритет.

2. **Шардирование задач сбора**
   - генерировать задачи per source/per category;
   - распределять через очередь Redis и несколько worker-инстансов.

3. **Ограничение нагрузки**
   - адаптивный rate limiting per-domain;
   - backoff на уровне источника;
   - circuit-breaker для нестабильных сайтов.

4. **Надежность и наблюдаемость**
   - метрики (Prometheus): latency, error-rate, success-rate, parsed items;
   - централизованные логи (ELK/OpenSearch/Grafana Loki);
   - alerting по SLA скрейпа.

5. **Эволюция схемы данных**
   - индексы на `price_history(product_source_id, created_at)`;
   - партиционирование `price_history` по времени;
   - архивирование старых периодов.

6. **Качество данных**
   - схема версий парсеров и feature flags;
   - автоматическая проверка аномалий (скачки/нулевые цены/дубликаты).