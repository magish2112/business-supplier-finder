#!/usr/bin/env python3
"""
Тест поиска с обновленным парсером
"""

from parser import CompanyParser
from config import CATEGORIES

def test_single_search():
    """Тест поиска по одной категории"""
    print("🔍 Тест поиска по категории 'Металлопрокат'")
    print("=" * 50)
    
    parser = CompanyParser()
    
    try:
        # Поиск только на Avito для теста
        print("Поиск на Avito...")
        companies = parser.search_avito("металлопрокат", "Металлопрокат")
        
        print(f"\n📊 Результаты:")
        print(f"Найдено компаний: {len(companies)}")
        
        if companies:
            print("\nНайденные компании:")
            for i, company in enumerate(companies, 1):
                print(f"{i}. {company.name}")
                print(f"   Категория: {company.category}")
                print(f"   Телефон: {company.phone or 'Не указан'}")
                print(f"   Адрес: {company.address or 'Не указан'}")
                print(f"   Источник: {company.source}")
                print()
        else:
            print("❌ Компании не найдены")
            
    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")
    finally:
        parser.close_driver()

def test_multiple_queries():
    """Тест поиска по нескольким запросам"""
    print("\n🔍 Тест поиска по нескольким запросам")
    print("=" * 50)
    
    parser = CompanyParser()
    
    queries = ["арматура", "трубы", "лист металлический"]
    
    all_companies = []
    
    try:
        for query in queries:
            print(f"\nПоиск: {query}")
            companies = parser.search_avito(query, "Металлопрокат")
            all_companies.extend(companies)
            print(f"Найдено: {len(companies)} компаний")
        
        print(f"\n📊 Общие результаты:")
        print(f"Всего найдено: {len(all_companies)} компаний")
        
        if all_companies:
            # Удаляем дубликаты
            unique_companies = []
            seen_names = set()
            
            for company in all_companies:
                normalized_name = company.name.lower().strip()
                if normalized_name not in seen_names:
                    seen_names.add(normalized_name)
                    unique_companies.append(company)
            
            print(f"Уникальных компаний: {len(unique_companies)}")
            
            print("\nПервые 5 компаний:")
            for i, company in enumerate(unique_companies[:5], 1):
                print(f"{i}. {company.name}")
                
    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")
    finally:
        parser.close_driver()

def main():
    """Главная функция"""
    print("🧪 Тест обновленного парсера")
    print("=" * 50)
    
    # Тест 1: Поиск по одной категории
    test_single_search()
    
    # Тест 2: Поиск по нескольким запросам
    test_multiple_queries()
    
    print("\n✅ Тестирование завершено!")

if __name__ == "__main__":
    main() 