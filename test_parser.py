#!/usr/bin/env python3
"""
Простой тест парсера поставщиков
"""

def test_imports():
    """Тест импортов"""
    print("🔧 Тестирование импортов...")
    
    try:
        from config import CATEGORIES, PARSER_CONFIG
        print("✅ config.py - OK")
    except Exception as e:
        print(f"❌ config.py - Ошибка: {e}")
        return False
    
    try:
        from models import Company, CompanyStatus
        print("✅ models.py - OK")
    except Exception as e:
        print(f"❌ models.py - Ошибка: {e}")
        return False
    
    try:
        from validator import CompanyValidator
        print("✅ validator.py - OK")
    except Exception as e:
        print(f"❌ validator.py - Ошибка: {e}")
        return False
    
    try:
        from excel_exporter import ExcelExporter
        print("✅ excel_exporter.py - OK")
    except Exception as e:
        print(f"❌ excel_exporter.py - Ошибка: {e}")
        return False
    
    try:
        from parser import CompanyParser
        print("✅ parser.py - OK")
    except Exception as e:
        print(f"❌ parser.py - Ошибка: {e}")
        return False
    
    try:
        from main import SupplierParser
        print("✅ main.py - OK")
    except Exception as e:
        print(f"❌ main.py - Ошибка: {e}")
        return False
    
    return True

def test_basic_functionality():
    """Тест базовой функциональности"""
    print("\n🔧 Тестирование базовой функциональности...")
    
    try:
        from models import Company, CompanyStatus
        from datetime import datetime
        
        # Создаем тестовую компанию
        company = Company(
            name="Тестовая компания",
            category="Металлопрокат",
            subcategory="арматура",
            phone="+7(999)123-45-67",
            email="test@example.com",
            website="https://example.com",
            status=CompanyStatus.ACTIVE,
            check_date=datetime.now(),
            source="Тест"
        )
        
        print(f"✅ Создана тестовая компания: {company.name}")
        
        # Тест преобразования в словарь
        data = company.to_dict()
        print(f"✅ Преобразование в словарь: {len(data)} полей")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка базовой функциональности: {e}")
        return False

def test_validator():
    """Тест валидатора"""
    print("\n🔧 Тестирование валидатора...")
    
    try:
        from validator import CompanyValidator
        from models import Company
        
        validator = CompanyValidator()
        print("✅ Валидатор создан")
        
        # Тест валидации телефона
        phone = "+7(999)123-45-67"
        is_valid = validator._check_phone(phone)
        print(f"✅ Валидация телефона {phone}: {is_valid}")
        
        # Тест валидации email
        email = "test@example.com"
        is_valid = validator._check_email(email)
        print(f"✅ Валидация email {email}: {is_valid}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка валидатора: {e}")
        return False

def test_excel_export():
    """Тест экспорта в Excel"""
    print("\n🔧 Тестирование экспорта в Excel...")
    
    try:
        from excel_exporter import ExcelExporter
        from models import Company, CompanyStatus
        from datetime import datetime
        
        # Создаем тестовые компании
        companies = [
            Company(
                name="Компания 1",
                category="Металлопрокат",
                subcategory="арматура",
                phone="+7(999)111-11-11",
                status=CompanyStatus.ACTIVE,
                check_date=datetime.now(),
                source="Тест"
            ),
            Company(
                name="Компания 2",
                category="Сантехника",
                subcategory="трубы",
                phone="+7(999)222-22-22",
                status=CompanyStatus.INACTIVE,
                check_date=datetime.now(),
                source="Тест"
            )
        ]
        
        # Экспортируем в Excel
        exporter = ExcelExporter()
        filename = exporter.export_companies(companies, "test_export.xlsx")
        print(f"✅ Экспорт в Excel: {filename}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка экспорта в Excel: {e}")
        return False

def test_config():
    """Тест конфигурации"""
    print("\n🔧 Тестирование конфигурации...")
    
    try:
        from config import CATEGORIES, PARSER_CONFIG, EXCEL_CONFIG
        
        print(f"✅ Категорий настроено: {len(CATEGORIES)}")
        for key, category in CATEGORIES.items():
            print(f"   - {category['name']}: {len(category['keywords'])} ключевых слов")
        
        print(f"✅ Настроек парсера: {len(PARSER_CONFIG)}")
        print(f"✅ Настроек Excel: {len(EXCEL_CONFIG)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🧪 Тестирование парсера поставщиков")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config,
        test_basic_functionality,
        test_validator,
        test_excel_export
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Результаты тестирования: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("✅ Все тесты пройдены! Парсер готов к работе.")
        print("\n🚀 Для запуска используйте:")
        print("   python main.py")
    else:
        print("❌ Некоторые тесты не пройдены. Проверьте установку зависимостей.")

if __name__ == "__main__":
    main() 