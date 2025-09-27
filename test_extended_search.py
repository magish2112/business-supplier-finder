#!/usr/bin/env python3
"""
Тест для проверки расширенной функциональности поиска поставщиков
"""

import os
import sys
from business_supplier_finder import BusinessSupplierFinder
from config import PARSER_CONFIG

def test_extended_search():
    """Тестирование расширенного поиска по множеству источников"""

    print("=" * 80)
    print("🔍 ТЕСТИРОВАНИЕ РАСШИРЕННОГО ПОИСКА ПОСТАВЩИКОВ")
    print("=" * 80)

    # Проверяем настройки
    print("\n⚙️  НАСТРОЙКИ ИСТОЧНИКОВ ПОИСКА:")
    print("-" * 50)

    settings = [
        ('Бизнес-каталоги', PARSER_CONFIG['use_business_catalogs']),
        ('Сайты компаний', PARSER_CONFIG['use_company_websites']),
        ('Соцсети', PARSER_CONFIG['use_social_media']),
        ('DuckDuckGo', PARSER_CONFIG['use_duckduckgo']),
        ('Bing', PARSER_CONFIG['use_bing'])
    ]

    for name, enabled in settings:
        status = "✅ Включен" if enabled else "❌ Выключен"
        print(f"{name}: {status}")

    # Инициализируем поисковик
    print("\n🚀 ИНИЦИАЛИЗАЦИЯ ПОИСКОВИКА:")
    print("-" * 50)

    finder = BusinessSupplierFinder()
    print("✅ Поисковик инициализирован")

    # Тестируем поиск по одному источнику
    test_sources = [
        ('Yandex Maps', lambda q, r: finder._search_yandex_maps(q, r)),
        ('RusList', lambda q, r: finder._search_ruslist(q, r)),
        ('YP Russia', lambda q, r: finder._search_yp_catalog(q, r)),
        ('DuckDuckGo', lambda q, r: finder._search_duckduckgo(q, r)),
        ('Bing', lambda q, r: finder._search_bing(q, r))
    ]

    print("\n🧪 ТЕСТИРОВАНИЕ ОТДЕЛЬНЫХ ИСТОЧНИКОВ:")
    print("-" * 50)

    test_product = "цемент"
    test_region = "Москва"

    total_results = 0

    for source_name, search_func in test_sources:
        try:
            print(f"\n🔍 Тестируем {source_name}...")
            results = search_func(test_product, test_region)
            print(f"   📊 Результатов: {len(results)}")

            if results:
                # Показываем первые 2 результата
                for i, result in enumerate(results[:2], 1):
                    name = result.get('name', 'Без названия')[:50]
                    source = result.get('source', 'Неизвестен')
                    print(f"   {i}. {name} ({source})")

            total_results += len(results)

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")

    print("\n" + "=" * 60)
    print("📈 СТАТИСТИКА ТЕСТИРОВАНИЯ:"    print("=" * 60)
    print(f"Всего протестировано источников: {len(test_sources)}")
    print(f"Общее количество результатов: {total_results}")
    print(".1f"
    print("\n🎯 РЕКОМЕНДАЦИИ:")
    print("-" * 30)

    if total_results == 0:
        print("❌ Ни один источник не вернул результатов")
        print("   Проверьте подключение к интернету")
        print("   Возможно, сайты заблокировали парсинг")

    elif total_results < 5:
        print("⚠️  Мало результатов - некоторые источники могут не работать")
        print("   Попробуйте включить дополнительные источники")

    else:
        print("✅ Хорошие результаты! Поиск работает корректно")
        print("   Можно использовать в продакшене")

    print("\n🔧 ДОСТУПНЫЕ ИСТОЧНИКИ:")
    print("-" * 30)
    print("• Яндекс.Карты - локальные организации")
    print("• 2GIS - геолокационные данные")
    print("• RusList - бизнес-справочник")
    print("• YP Russia - желтые страницы")
    print("• Yell.ru - телефонный справочник")
    print("• BizDir - бизнес-каталог")
    print("• FirmCard - карточки компаний")
    print("• OrgPage - страницы организаций")
    print("• AllBiz - B2B платформа")
    print("• DuckDuckGo - приватный поиск")
    print("• Bing - поисковая система")
    print("• VK Business - бизнес-сообщества")
    print("• Telegram - бизнес-каналы")

    print("\n💡 СОВЕТЫ ПО ОПТИМИЗАЦИИ:")
    print("-" * 35)
    print("• Используйте несколько источников для лучших результатов")
    print("• Настройте задержки между запросами для избежания блокировок")
    print("• Включайте только необходимые источники для скорости")
    print("• Мониторьте логи для выявления проблемных источников")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_extended_search()
