#!/usr/bin/env python3
"""
Пример использования парсера поставщиков
"""

from main import SupplierParser
from config import CATEGORIES

def example_basic_usage():
    """Базовый пример использования"""
    print("🔧 Пример базового использования парсера")
    print("=" * 50)
    
    # Создаем экземпляр парсера
    parser = SupplierParser()
    
    # Поиск компаний в категории металлопрокат
    print("\n1. Поиск компаний в категории 'Металлопрокат'")
    companies = parser.search_by_category('metalloprokat')
    
    if companies:
        print(f"✅ Найдено {len(companies)} компаний")
        
        # Показываем первые 3 компании
        for i, company in enumerate(companies[:3], 1):
            print(f"\n{i}. {company.name}")
            print(f"   Категория: {company.category}")
            print(f"   Телефон: {company.phone or 'Не указан'}")
            print(f"   Источник: {company.source}")
    else:
        print("❌ Компании не найдены")

def example_validation():
    """Пример валидации компаний"""
    print("\n🔍 Пример валидации компаний")
    print("=" * 50)
    
    parser = SupplierParser()
    
    # Поиск компаний
    companies = parser.search_by_category('santehnika', ['трубы', 'краны'])
    
    if companies:
        print(f"Найдено {len(companies)} компаний для валидации")
        
        # Валидация
        validated_companies = parser.validate_companies(companies)
        
        # Показываем результаты
        active_count = sum(1 for c in validated_companies if c.status.value == 'Работает')
        print(f"\n📊 Результаты валидации:")
        print(f"Работает: {active_count}")
        print(f"Не работает: {len(validated_companies) - active_count}")
        
        # Показываем работающие компании
        working_companies = [c for c in validated_companies if c.status.value == 'Работает']
        if working_companies:
            print(f"\n✅ Работающие компании:")
            for company in working_companies[:3]:
                print(f"- {company.name} ({company.phone})")

def example_excel_export():
    """Пример экспорта в Excel"""
    print("\n📊 Пример экспорта в Excel")
    print("=" * 50)
    
    parser = SupplierParser()
    
    # Поиск по нескольким категориям
    all_companies = []
    
    categories_to_search = ['metalloprokat', 'santehnika', 'stroymaterialy']
    
    for category in categories_to_search:
        print(f"\nПоиск в категории: {CATEGORIES[category]['name']}")
        companies = parser.search_by_category(category)
        all_companies.extend(companies)
    
    if all_companies:
        print(f"\nВсего найдено: {len(all_companies)} компаний")
        
        # Валидация
        validated_companies = parser.validate_companies(all_companies)
        
        # Экспорт в Excel
        filename = parser.export_to_excel(validated_companies)
        print(f"\n✅ Данные экспортированы в файл: {filename}")

def example_custom_search():
    """Пример кастомного поиска"""
    print("\n🎯 Пример кастомного поиска")
    print("=" * 50)
    
    parser = SupplierParser()
    
    # Кастомные поисковые запросы
    custom_queries = ['арматура А500С', 'труба профильная', 'лист оцинкованный']
    
    all_companies = []
    
    for query in custom_queries:
        print(f"\nПоиск: {query}")
        result = parser.parser.search_all_sources(query, 'Металлопрокат')
        all_companies.extend(result.companies)
        print(f"Найдено: {len(result.companies)} компаний")
    
    if all_companies:
        # Удаляем дубликаты
        unique_companies = parser._remove_duplicates(all_companies)
        print(f"\nУникальных компаний: {len(unique_companies)}")
        
        # Валидация и экспорт
        validated_companies = parser.validate_companies(unique_companies)
        filename = parser.export_to_excel(validated_companies, 'custom_search_results.xlsx')
        print(f"Результаты сохранены в: {filename}")

def example_statistics():
    """Пример получения статистики"""
    print("\n📈 Пример получения статистики")
    print("=" * 50)
    
    parser = SupplierParser()
    
    # Поиск по всем категориям
    all_companies = parser.search_all_categories()
    
    if all_companies:
        # Валидация
        validated_companies = parser.validate_companies(all_companies)
        
        # Получаем статистику
        summary = parser.validator.get_validation_summary(validated_companies)
        
        print(f"\n📊 Общая статистика:")
        print(f"Всего компаний: {summary['total']}")
        print(f"Работает: {summary['active']} ({summary['active_percentage']:.1f}%)")
        print(f"Не работает: {summary['inactive']}")
        print(f"Неизвестно: {summary['unknown']}")
        
        # Статистика по категориям
        print(f"\n📋 Статистика по категориям:")
        categories = {}
        for company in validated_companies:
            if company.category not in categories:
                categories[company.category] = {'total': 0, 'active': 0}
            categories[company.category]['total'] += 1
            if company.status.value == 'Работает':
                categories[company.category]['active'] += 1
        
        for category, stats in categories.items():
            percentage = (stats['active'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"{category}: {stats['active']}/{stats['total']} ({percentage:.1f}%)")

def main():
    """Запуск всех примеров"""
    print("🏗️  Примеры использования парсера поставщиков")
    print("=" * 60)
    
    try:
        # Пример 1: Базовое использование
        example_basic_usage()
        
        # Пример 2: Валидация
        example_validation()
        
        # Пример 3: Экспорт в Excel
        example_excel_export()
        
        # Пример 4: Кастомный поиск
        example_custom_search()
        
        # Пример 5: Статистика
        example_statistics()
        
        print("\n✅ Все примеры выполнены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении примеров: {e}")
        print("Убедитесь, что все зависимости установлены и Chrome браузер доступен")

if __name__ == "__main__":
    main() 