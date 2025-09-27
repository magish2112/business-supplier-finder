#!/usr/bin/env python3
"""
Тест для проверки интеграции Perplexity API
"""

import os
import sys
from business_supplier_finder import BusinessSupplierFinder
from config import PERPLEXITY_CONFIG

def test_perplexity_integration():
    """Тестирование интеграции Perplexity API"""

    print("=" * 80)
    print("🤖 ТЕСТИРОВАНИЕ ИНТЕГРАЦИИ PERPLEXITY API")
    print("=" * 80)

    # Проверяем настройки
    print("\n⚙️  ПРОВЕРКА НАСТРОЕК:")
    print("-" * 40)

    api_key = os.getenv('PERPLEXITY_API_KEY') or PERPLEXITY_CONFIG['api_key']
    enabled = PERPLEXITY_CONFIG['enabled']

    print(f"API Key: {'✅ Настроен' if api_key else '❌ Отсутствует'}")
    print(f"Включен: {'✅ Да' if enabled else '❌ Нет'}")
    print(f"Модель: {PERPLEXITY_CONFIG['model']}")
    print(f"Max Tokens: {PERPLEXITY_CONFIG['max_tokens']}")
    print(f"Timeout: {PERPLEXITY_CONFIG['search_timeout']} сек")

    # Инициализируем поисковик
    print("\n🚀 ИНИЦИАЛИЗАЦИЯ ПОИСКОВИКА:")
    print("-" * 40)

    finder = BusinessSupplierFinder()

    if finder.perplexity_client:
        print("✅ Perplexity клиент инициализирован")
    else:
        print("❌ Perplexity клиент не инициализирован")
        if not enabled:
            print("ℹ️  Причина: PERPLEXITY_ENABLED=false")
        elif not api_key:
            print("ℹ️  Причина: Отсутствует PERPLEXITY_API_KEY")
        else:
            print("ℹ️  Причина: Другая ошибка инициализации")

    # Тестируем поиск (если API настроен)
    if finder.perplexity_client:
        print("\n🔍 ТЕСТИРОВАНИЕ ПОИСКА:")
        print("-" * 40)

        test_product = "цемент"
        test_region = "Москва"

        print(f"Поиск: {test_product} в {test_region}")

        try:
            # Тестируем Perplexity поиск напрямую
            perplexity_results = finder._search_perplexity_suppliers(test_product, test_region)

            print("\n📊 РЕЗУЛЬТАТЫ:")
            print(f"Найдено поставщиков: {len(perplexity_results)}")

            if perplexity_results:
                print("\n🎯 ПЕРВЫЕ 3 РЕЗУЛЬТАТА:")
                for i, supplier in enumerate(perplexity_results[:3], 1):
                    print(f"\n{i}. {supplier.get('name', 'Без названия')}")
                    print(f"   Тип: {supplier.get('company_type', 'Неизвестен')}")
                    print(f"   Рейтинг: {supplier.get('relevance_score', 0)}")
                    print(f"   Телефон: {supplier.get('phone', 'Не указан')}")
                    print(f"   Email: {supplier.get('email', 'Не указан')}")
                    print(f"   Сайт: {supplier.get('website', 'Не указан')}")
                    if supplier.get('ai_generated'):
                        print("   🤖 AI-generated")
            else:
                print("❌ Результаты не найдены")

        except Exception as e:
            print(f"❌ Ошибка при поиске: {e}")

    print("\n" + "=" * 80)
    print("📋 РЕКОМЕНДАЦИИ:")
    print("=" * 80)

    if not api_key:
        print("1. 🔑 Добавьте PERPLEXITY_API_KEY в .env файл")
        print("2. 📖 Получите ключ на: https://www.perplexity.ai/settings/api")
        print("3. ⚙️  Установите PERPLEXITY_ENABLED=true")

    if not enabled:
        print("1. ⚙️  Установите PERPLEXITY_ENABLED=true в .env файле")

    if finder.perplexity_client:
        print("✅ Perplexity API готов к работе!")
        print("🎯 Поиск теперь использует AI для улучшения результатов")
    else:
        print("⚠️  Perplexity API не настроен. Поиск будет работать в обычном режиме.")

    print("\n💡 ПРЕИМУЩЕСТВА PERPLEXITY API:")
    print("- 🎯 Более точные результаты поиска")
    print("- 🤖 Понимание бизнес-контекста")
    print("- 📞 Автоматическое извлечение контактов")
    print("- ⭐ Высокий рейтинг AI-результатов")
    print("- 🚀 Быстрая обработка запросов")

    print("=" * 80)

if __name__ == "__main__":
    test_perplexity_integration()
