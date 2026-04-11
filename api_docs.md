# 🔌 API Документация - Поиск поставщиков v2.3

## Обзор

REST API для поиска бизнес-поставщиков с использованием множественных источников и AI-усиления.

**Базовый URL:** `http://localhost:5000/api/v1`

## Аутентификация

API не требует аутентификации для базовых операций.

### Опциональный API-ключ (`API_KEY` / `X-API-Key`)

Если в окружении задана непустая переменная **`API_KEY`**, для перечисленных ниже JSON-маршрутов нужен заголовок **`X-API-Key: <ключ>`** либо **`Authorization: Bearer <ключ>`**. Иначе ответ **`401`** с объектом ошибки (`code`: `unauthorized`).

Защищаются префиксы:

- `/api/v1/search` (включая `GET`/`POST`)
- `/api/v1/suppliers`
- `/api/v1/stats`
- `/api/v2/`
- `/api/quick_search/`
- `/api/saved_search/`

Без ключа по-прежнему доступны **`/api/v1/health`**, **`/api/v1/config`** и HTML-страницы. Если задано **`API_KEY_REQUIRED=true`**, при пустом **`API_KEY`** приложение не запустится.

## Endpoints

### 🔍 Поиск поставщиков

**POST** `/api/v1/search`

Запускает асинхронный поиск поставщиков.

#### Параметры запроса
```json
{
  "product": "string (обязательно)",
  "region": "string (опционально)",
  "quantity": "string (опционально)"
}
```

#### Пример запроса
```bash
curl -X POST http://localhost:5000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "product": "Grohe New Tempesta 110",
    "region": "Ставрополь",
    "quantity": "100"
  }'
```

#### Пример ответа
```json
{
  "success": true,
  "search_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "accepted",
  "message": "Поиск запущен в фоне",
  "estimated_time": "30-120 секунд"
}
```

### 📊 Получение результатов поиска

**GET** `/api/v1/search/{search_id}`

Получает результаты поиска по его ID.

#### Параметры пути
- `search_id` (string): Уникальный идентификатор поиска

#### Поле `status`

Возможные значения:

- **`in_progress`** — поиск ещё выполняется (поле `message` с пояснением).
- **`completed`** — успешно завершён; данные в `data` (поставщики и метаданные поиска).
- **`failed`** — ошибка выполнения; в теле ответа объект **`error`** с полями `code` и `message` (например, `search_failed` и текст об ошибке поиска).

#### Пример запроса
```bash
curl http://localhost:5000/api/v1/search/123e4567-e89b-12d3-a456-426614174000
```

#### Пример ответа (выполняется)
```json
{
  "status": "in_progress",
  "search_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Поиск ещё выполняется"
}
```

#### Пример ответа (ошибка)
```json
{
  "status": "failed",
  "search_id": "123e4567-e89b-12d3-a456-426614174000",
  "error": {
    "code": "search_failed",
    "message": "Ошибка при выполнении поиска"
  }
}
```

#### Пример ответа (завершено)
```json
{
  "status": "completed",
  "search_id": "123e4567-e89b-12d3-a456-426614174000",
  "data": {
    "suppliers": [...],
    "product": "Grohe New Tempesta 110",
    "region": "Ставрополь",
    "quantity": "100",
    "completed_at": "2025-01-27T10:30:00",
    "total": 45
  }
}
```

### 📋 Список поставщиков

**GET** `/api/v1/suppliers`

Получает поставщиков с фильтрацией и пагинацией.

#### Query параметры
- `search_id` (string, опционально): UUID задачи из ответа **POST** `/api/v1/search`. Если указан — выборка из завершённой задачи с этим идентификатором. Если не указан — используется глобальный результат последнего поиска (UI / legacy).
- `type` (string): Фильтр по типу компании (`PRODUCER`, `DISTRIBUTOR`, etc.)
- `min_score` (integer): Минимальный рейтинг релевантности (0-100)
- `limit` (integer): Количество результатов на страницу (по умолчанию 50)
- `offset` (integer): Смещение для пагинации (по умолчанию 0)

#### Пример запроса
```bash
curl "http://localhost:5000/api/v1/suppliers?search_id=123e4567-e89b-12d3-a456-426614174000&type=PRODUCER&min_score=80&limit=20"
```

#### Пример ответа
```json
{
  "success": true,
  "data": {
    "suppliers": [
      {
        "name": "ООО Рога и Копыта",
        "company_type": "PRODUCER",
        "relevance_score": 95,
        "phone": "+7 (495) 123-45-67",
        "email": "info@roga-kopita.ru",
        "website": "https://roga-kopita.ru",
        "address": "г. Москва, ул. Ленина, 10",
        "contact_completeness": 100
      }
    ],
    "total": 150,
    "limit": 20,
    "offset": 0
  }
}
```

### 📈 Статистика

**GET** `/api/v1/stats`

Получает статистику приложения и текущего поиска.

В объекте `stats`:

- **`http_cache_entries`** — число записей во внутреннем HTTP-кэше.
- **`api_search_jobs`** — агрегированные счётчики фоновых задач поиска по статусам: `in_progress`, `completed`, `failed`.

#### Пример запроса
```bash
curl http://localhost:5000/api/v1/stats
```

#### Пример ответа
```json
{
  "success": true,
  "stats": {
    "total_suppliers": 45,
    "http_cache_entries": 12,
    "api_search_jobs": {
      "in_progress": 1,
      "completed": 8,
      "failed": 0
    },
    "company_types": {
      "PRODUCER": 15,
      "DISTRIBUTOR": 20,
      "WHOLESALE_SUPPLIER": 10
    },
    "average_score": 78.5,
    "average_contacts": 85.2,
    "timestamp": "2025-01-27T10:30:00"
  }
}
```

### 💚 Проверка здоровья

**GET** `/api/v1/health`

Проверяет работоспособность сервиса.

#### Пример запроса
```bash
curl http://localhost:5000/api/v1/health
```

#### Пример ответа
```json
{
  "status": "healthy",
  "timestamp": "2025-01-27T10:30:00",
  "version": "2.3",
  "services": {
    "perplexity_ai": true,
    "web_scraping": true,
    "caching": true
  }
}
```

### ⚙️ Конфигурация

**GET** `/api/v1/config`

Получает информацию о конфигурации приложения.

#### Пример запроса
```bash
curl http://localhost:5000/api/v1/config
```

#### Пример ответа
```json
{
  "version": "2.3",
  "features": {
    "perplexity_ai": true,
    "multiple_sources": true,
    "advanced_scoring": true,
    "caching": true,
    "export": true
  },
  "sources": [
    "Google Search",
    "Yandex Search",
    "Yandex Maps",
    "2GIS",
    "Business Catalogs",
    "Perplexity AI"
  ]
}
```

## Коды ответов

- `200` - Успешный запрос
- `400` - Ошибка в данных запроса
- `404` - Ресурс не найден
- `500` - Внутренняя ошибка сервера

## Модель данных поставщика

```json
{
  "name": "string",
  "company_type": "PRODUCER|DISTRIBUTOR|WHOLESALE_SUPPLIER|RETAIL_SUPPLIER|WAREHOUSE|UNKNOWN",
  "company_size": "LARGE|MEDIUM|SMALL|UNKNOWN",
  "relevance_score": "integer (0-100)",
  "contact_completeness": "integer (0-100)",
  "phone": "string|null",
  "email": "string|null",
  "website": "string|null",
  "address": "string|null",
  "business_indicators": ["string"],
  "source": "string",
  "notes": "string|null"
}
```

## Ограничения

- Максимальное время выполнения поиска: 120 секунд
- Максимальное количество одновременных поисков: 5
- Кэширование результатов: 5 минут

## Примеры использования

### Python клиент
```python
import requests

# Запуск поиска
response = requests.post('http://localhost:5000/api/v1/search', json={
    'product': 'сварочный аппарат',
    'region': 'Москва',
    'quantity': '50'
})

search_id = response.json()['search_id']

# Проверка статуса
import time
while True:
    status = requests.get(f'http://localhost:5000/api/v1/search/{search_id}')
    if status.json()['status'] == 'completed':
        break
    time.sleep(5)

# Получение результатов
results = requests.get(f'http://localhost:5000/api/v1/search/{search_id}')
suppliers = results.json()['data']['suppliers']
```

### JavaScript клиент
```javascript
// Запуск поиска
fetch('/api/v1/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    product: 'трубы стальные',
    region: 'СПб'
  })
})
.then(res => res.json())
.then(data => {
  const searchId = data.search_id;

  // Проверка статуса каждые 10 секунд
  const checkStatus = setInterval(() => {
    fetch(`/api/v1/search/${searchId}`)
    .then(res => res.json())
    .then(status => {
      if (status.status === 'completed') {
        clearInterval(checkStatus);
        console.log('Результаты:', status.data.suppliers);
      }
    });
  }, 10000);
});
```

---

**Версия API:** v1
**Дата:** 2025
**Контакты:** Для вопросов по API обращайтесь к разработчику
