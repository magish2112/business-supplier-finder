# Makefile для проекта поиска поставщиков

.PHONY: help install dev-install test lint format clean docker-build docker-run docker-stop

# По умолчанию показываем помощь
help: ## Показать эту справку
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# Установка зависимостей
install: ## Установить основные зависимости
	pip install -r requirements.txt

dev-install: ## Установить зависимости для разработки
	pip install -r requirements.txt
	pip install pytest pytest-cov black isort flake8 mypy bandit

# Тестирование
test: ## Запустить все тесты
	pytest -v --cov=. --cov-report=html

test-unit: ## Запустить модульные тесты
	pytest tests/ -v

test-integration: ## Запустить интеграционные тесты
	pytest tests/test_integration.py -v

# Качество кода
lint: ## Проверить качество кода
	flake8 .
	mypy . --ignore-missing-imports

format: ## Форматировать код
	black .
	isort .

format-check: ## Проверить форматирование кода
	black --check .
	isort --check-only .

security: ## Проверить безопасность кода
	bandit -r .

# Docker
docker-build: ## Собрать Docker образ
	docker build -t supplier-finder .

docker-run: ## Запустить приложение в Docker
	docker run -p 5000:5000 --env-file .env supplier-finder

docker-compose-up: ## Запустить с помощью docker-compose
	docker-compose up --build

docker-compose-down: ## Остановить docker-compose
	docker-compose down

# Очистка
clean: ## Очистить временные файлы
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +

clean-all: clean ## Полная очистка включая логи и кэш
	rm -rf logs/
	rm -f *.log
	rm -f web_search_*.json
	rm -f business_search_*.json
	rm -f *.xlsx

# Запуск
run: ## Запустить приложение локально
	python web_app.py

run-debug: ## Запустить приложение в режиме отладки
	export FLASK_DEBUG=true && python web_app.py

# Документация
docs: ## Сгенерировать документацию
	@echo "Документация API: api_docs.md"
	@echo "Основная документация: README.md"

# CI/CD команды
ci: lint test security ## Запустить все проверки CI
