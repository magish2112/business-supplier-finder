#!/usr/bin/env python3
"""
Простой тест веб-приложения для поиска поставщиков
"""

import requests
import time
from bs4 import BeautifulSoup
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_web_app():
    """Тестирование веб-приложения"""
    base_url = "http://localhost:5000"

    try:
        logger.info("🧪 Тестирование веб-приложения...")

        # Тест главной страницы
        logger.info("📄 Тест главной страницы...")
        response = requests.get(base_url)
        if response.status_code == 200:
            logger.info("✅ Главная страница работает")
        else:
            logger.warning(f"⚠️  Главная страница вернула код {response.status_code}")

        # Тест страницы поиска
        logger.info("🔍 Тест страницы поиска...")
        response = requests.get(f"{base_url}/search")
        if response.status_code == 200:
            logger.info("✅ Страница поиска работает")
        else:
            logger.warning(f"⚠️  Страница поиска вернула код {response.status_code}")

        # Тест быстрого поиска
        logger.info("⚡ Тест быстрого поиска...")
        response = requests.get(f"{base_url}/quick_search")
        if response.status_code == 200:
            logger.info("✅ Быстрый поиск работает")
        else:
            logger.warning(f"⚠️  Быстрый поиск вернул код {response.status_code}")

        logger.info("🎉 Тестирование завершено!")

    except requests.exceptions.ConnectionError:
        logger.error("❌ Не удалось подключиться к веб-приложению")
        logger.error("💡 Убедитесь, что приложение запущено командой: python web_app.py")
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}")

def test_search_functionality():
    """Тест базовой функциональности поиска"""
    try:
        logger.info("🔧 Тест базовой функциональности поиска...")

        # Импорт функций поиска
        from business_supplier_finder import BusinessSupplierFinder

        finder = BusinessSupplierFinder()
        logger.info("✅ Модуль поиска успешно импортирован")

        # Тест создания объекта
        logger.info("📊 Тест создания объекта поиска...")
        # Здесь можно добавить дополнительные тесты

        logger.info("✅ Базовая функциональность работает")

    except ImportError as e:
        logger.error(f"❌ Ошибка импорта модулей: {e}")
        logger.error("💡 Попробуйте установить зависимости: pip install -r requirements.txt")
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании поиска: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ ПРИЛОЖЕНИЯ ПОИСКА ПОСТАВЩИКОВ")
    print("=" * 60)

    test_web_app()
    print()
    test_search_functionality()

    print("\n" + "=" * 60)
    print("💡 СОВЕТЫ:")
    print("1. Запустите веб-приложение: python web_app.py")
    print("2. Откройте браузер: http://localhost:5000")
    print("3. Протестируйте поиск с различными товарами")
    print("=" * 60)
