#!/usr/bin/env python3
"""
Улучшенный парсер поставщиков строительных материалов
С фокусом на производителей, дистрибьюторов и крупных поставщиков
Автор: AI Assistant
Версия: 2.3
"""

import sys
import time
import logging
from datetime import datetime
from typing import List, Optional

from config import CATEGORIES, logger, PARSER_CONFIG
from parser import CompanyParser
from validator import CompanyValidator
from excel_exporter import ExcelExporter
from models import Company, CompanyType, CompanySize

class SupplierParser:
    """Основной класс парсера поставщиков"""
    
    def __init__(self):
        self.parser = CompanyParser()
        self.validator = CompanyValidator()
        self.exporter = ExcelExporter()
        self.companies = []
        
    def search_by_category(self, category_key: str, search_terms: List[str] = None):
        """Поиск компаний по категории"""
        if category_key not in CATEGORIES:
            logger.error(f"Категория '{category_key}' не найдена")
            return []

        category = CATEGORIES[category_key]
        category_name = category['name']

        if not search_terms:
            search_terms = category.get('keywords', [])

        logger.info(f"🔍 Поиск компаний в категории: {category_name}")
        logger.info(f"📝 Поисковые запросы: {', '.join(search_terms)}")

        # Добавляем специфические запросы для производителей и дистрибьюторов
        enhanced_search_terms = search_terms.copy()
        if 'producer_keywords' in category:
            enhanced_search_terms.extend(category['producer_keywords'])
        if 'supplier_keywords' in category:
            enhanced_search_terms.extend(category['supplier_keywords'])

        logger.info(f"📋 Всего запросов после расширения: {len(enhanced_search_terms)}")
        search_terms = list(set(enhanced_search_terms))  # Убираем дубликаты
        
        all_companies = []
        
        for i, term in enumerate(search_terms, 1):
            logger.info(f"[{i}/{len(search_terms)}] Поиск по запросу: '{term}'")
            try:
                result = self.parser.search_all_sources(term, category_name)
                all_companies.extend(result.companies)
                logger.info(f"Найдено компаний: {len(result.companies)}")
                time.sleep(PARSER_CONFIG['delay_between_requests'])
            except Exception as e:
                logger.error(f"Ошибка при поиске '{term}': {e}")
                continue

        # Удаляем дубликаты и ранжируем
        unique_companies = self._remove_duplicates_and_rank(all_companies, category_key)
        logger.info(f"✅ Всего уникальных компаний найдено: {len(unique_companies)}")

        # Логируем статистику по типам компаний
        company_types = {}
        for company in unique_companies:
            if hasattr(company, 'company_type'):
                company_type = company.company_type.value if hasattr(company.company_type, 'value') else str(company.company_type)
            else:
                company_type = 'unknown'
            company_types[company_type] = company_types.get(company_type, 0) + 1

        logger.info(f"📊 Распределение компаний: {company_types}")

        return unique_companies
    
    def search_all_categories(self):
        """Поиск по всем категориям"""
        all_companies = []
        
        for category_key, category_info in CATEGORIES.items():
            print(f"\n{'='*50}")
            print(f"Поиск в категории: {category_info['name']}")
            print(f"{'='*50}")
            
            companies = self.search_by_category(category_key)
            all_companies.extend(companies)
            
        return all_companies
    
    def validate_companies(self, companies: List[Company]):
        """Валидация компаний"""
        if not companies:
            print("Нет компаний для валидации")
            return []
            
        print(f"\n🔍 Валидация {len(companies)} компаний...")
        
        validated_companies = self.validator.validate_batch(companies)
        
        # Получаем сводку
        summary = self.validator.get_validation_summary(validated_companies)
        
        print(f"\n📊 Результаты валидации:")
        print(f"Всего: {summary['total']}")
        print(f"Работает: {summary['active']} ({summary['active_percentage']:.1f}%)")
        print(f"Не работает: {summary['inactive']}")
        print(f"Неизвестно: {summary['unknown']}")
        
        return validated_companies
    
    def export_to_excel(self, companies: List[Company], filename: str = None):
        """Экспорт в Excel"""
        if not companies:
            print("Нет данных для экспорта")
            return
            
        print(f"\n📊 Экспорт {len(companies)} компаний в Excel...")
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"suppliers_{timestamp}.xlsx"
            
        self.exporter.export_companies(companies, filename)
        
        return filename
    
    def _remove_duplicates_and_rank(self, companies: List[Company], category_key: str) -> List[Company]:
        """Удаление дубликатов и ранжирование компаний с фокусом на производителей"""
        seen_names = set()
        unique_companies = []

        for company in companies:
            # Нормализуем название для сравнения
            normalized_name = company.name.lower().strip()

            if normalized_name not in seen_names and len(normalized_name) > 2:
                seen_names.add(normalized_name)

                # Автоматическая классификация типа компании
                company.company_type = self._classify_company_from_name(company.name, category_key)

                # Расчет релевантности
                company.calculate_relevance_score()

                unique_companies.append(company)

        # Сортировка по релевантности (производители и дистрибьюторы в приоритете)
        unique_companies.sort(key=lambda x: (
            0 if hasattr(x, 'company_type') and x.company_type == CompanyType.PRODUCER else
            1 if hasattr(x, 'company_type') and x.company_type == CompanyType.DISTRIBUTOR else
            2 if hasattr(x, 'company_type') and x.company_type == CompanyType.WHOLESALE_SUPPLIER else 3,
            x.relevance_score if hasattr(x, 'relevance_score') else 0
        ), reverse=True)

        return unique_companies[:100]  # Ограничиваем до 100 лучших компаний

    def _classify_company_from_name(self, name: str, category_key: str) -> CompanyType:
        """Классификация типа компании по названию"""
        name_lower = name.lower()

        # Ключевые слова для производителей
        producer_keywords = ['завод', 'фабрика', 'производитель', 'производство', 'изготовитель', 'выпускает']
        if any(keyword in name_lower for keyword in producer_keywords):
            return CompanyType.PRODUCER

        # Ключевые слова для дистрибьюторов
        distributor_keywords = ['дистрибьютор', 'официальный', 'представительство', 'партнер']
        if any(keyword in name_lower for keyword in distributor_keywords):
            return CompanyType.DISTRIBUTOR

        # Ключевые слова для оптовых поставщиков
        wholesale_keywords = ['опт', 'склад', 'база', 'поставщик', 'компания']
        if any(keyword in name_lower for keyword in wholesale_keywords):
            return CompanyType.WHOLESALE_SUPPLIER

        return CompanyType.UNKNOWN
    
    def run_interactive(self):
        """Интерактивный режим работы"""
        print("🏗️  Парсер поставщиков строительных материалов")
        print("=" * 50)
        
        while True:
            print("\nВыберите действие:")
            print("1. Поиск по конкретной категории")
            print("2. Поиск по всем категориям")
            print("3. Валидация существующих данных")
            print("4. Экспорт в Excel")
            print("5. Полный цикл (поиск + валидация + экспорт)")
            print("0. Выход")
            
            choice = input("\nВведите номер: ").strip()
            
            if choice == "0":
                print("До свидания!")
                break
                
            elif choice == "1":
                self._handle_category_search()
                
            elif choice == "2":
                self._handle_all_categories_search()
                
            elif choice == "3":
                self._handle_validation()
                
            elif choice == "4":
                self._handle_export()
                
            elif choice == "5":
                self._handle_full_cycle()
                
            else:
                print("Неверный выбор. Попробуйте снова.")
    
    def _handle_category_search(self):
        """Обработка поиска по категории"""
        print("\nДоступные категории:")
        for i, (key, category) in enumerate(CATEGORIES.items(), 1):
            print(f"{i}. {category['name']}")
            
        try:
            choice = int(input("\nВыберите категорию (номер): ")) - 1
            category_keys = list(CATEGORIES.keys())
            
            if 0 <= choice < len(category_keys):
                category_key = category_keys[choice]
                companies = self.search_by_category(category_key)
                self.companies.extend(companies)
                print(f"\n✅ Добавлено {len(companies)} компаний")
            else:
                print("Неверный номер категории")
                
        except ValueError:
            print("Введите корректный номер")
    
    def _handle_all_categories_search(self):
        """Обработка поиска по всем категориям"""
        print("\n🔍 Поиск по всем категориям...")
        companies = self.search_all_categories()
        self.companies = companies
        print(f"\n✅ Найдено {len(companies)} компаний")
    
    def _handle_validation(self):
        """Обработка валидации"""
        if not self.companies:
            print("Нет данных для валидации. Сначала выполните поиск.")
            return
            
        print(f"\n🔍 Валидация {len(self.companies)} компаний...")
        self.companies = self.validate_companies(self.companies)
    
    def _handle_export(self):
        """Обработка экспорта"""
        if not self.companies:
            print("Нет данных для экспорта. Сначала выполните поиск.")
            return
            
        filename = input("\nВведите имя файла (или Enter для авто): ").strip()
        if not filename:
            filename = None
            
        exported_file = self.export_to_excel(self.companies, filename)
        print(f"✅ Данные экспортированы в {exported_file}")
    
    def _handle_full_cycle(self):
        """Полный цикл работы"""
        print("\n🚀 Запуск полного цикла...")
        
        # Поиск
        print("\n1️⃣  Этап: Поиск компаний")
        companies = self.search_all_categories()
        
        # Валидация
        print("\n2️⃣  Этап: Валидация компаний")
        validated_companies = self.validate_companies(companies)
        
        # Экспорт
        print("\n3️⃣  Этап: Экспорт в Excel")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"suppliers_full_cycle_{timestamp}.xlsx"
        exported_file = self.export_to_excel(validated_companies, filename)
        
        print(f"\n✅ Полный цикл завершен!")
        print(f"📁 Файл: {exported_file}")
        print(f"📊 Компаний обработано: {len(validated_companies)}")
        
        self.companies = validated_companies

def main():
    """Главная функция"""
    parser = SupplierParser()
    
    if len(sys.argv) > 1:
        # Командная строка
        command = sys.argv[1]
        
        if command == "search":
            if len(sys.argv) > 2:
                category = sys.argv[2]
                companies = parser.search_by_category(category)
                parser.companies = companies
            else:
                print("Укажите категорию для поиска")
                
        elif command == "validate":
            if parser.companies:
                parser.companies = parser.validate_companies(parser.companies)
            else:
                print("Нет данных для валидации")
                
        elif command == "export":
            if parser.companies:
                filename = sys.argv[2] if len(sys.argv) > 2 else None
                parser.export_to_excel(parser.companies, filename)
            else:
                print("Нет данных для экспорта")
                
        elif command == "full":
            parser._handle_full_cycle()
            
    else:
        # Интерактивный режим
        parser.run_interactive()

if __name__ == "__main__":
    main() 