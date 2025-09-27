#!/usr/bin/env python3
"""
Тест для проверки отображения ссылок в результатах поиска
"""

from business_supplier_finder import BusinessSupplierFinder
from models import Company, CompanyType, CompanySize
import datetime

def test_link_display():
    """Тестирование отображения ссылок с длинными URL"""

    # Создаем тестовые данные с длинными ссылками
    test_suppliers = [
        {
            'name': 'Тестовая Компания Производитель',
            'phone': '+7 (495) 123-45-67',
            'email': 'info@very-long-domain-name-company-production-factory-manufacturer-supplier-store-shop-center.ru',
            'website': 'https://www.very-long-domain-name-company-production-factory-manufacturer-supplier-store-shop-center-marketplace-online-shop-catalog-database-system-platform.ru/products/building-materials/construction-supplies/metal-products/steel-pipes/round-pipes/diameter-50-wall-3-length-6000',
            'source': 'Test Source',
            'is_business': True,
            'company_type': 'producer',
            'relevance_score': 85,
            'contact_completeness': 100,
            'business_indicators': ['производитель', 'завод', 'опт']
        },
        {
            'name': 'Дистрибьютор Строительных Материалов',
            'phone': '+7 (812) 987-65-43',
            'email': 'sales@construction-materials-distributor-wholesale-supplier-building-materials-construction-supplies-hardware-tools-equipment-machinery-parts-components-accessories-online-store.ru',
            'website': 'https://construction-materials-distributor-wholesale-supplier-building-materials-construction-supplies-hardware-tools-equipment-machinery-parts-components-accessories-online-store-catalog-price-list-contacts-delivery-payment-terms.ru/catalog/metal-products/steel-sheets/hot-rolled/cold-rolled/galvanized/corrosion-resistant/thickness-2mm-width-1250mm-length-2500mm',
            'source': 'Test Source 2',
            'is_business': True,
            'company_type': 'distributor',
            'relevance_score': 78,
            'contact_completeness': 100,
            'business_indicators': ['дистрибьютор', 'опт', 'поставщик']
        }
    ]

    print("=" * 80)
    print("🧪 ТЕСТИРОВАНИЕ ОТОБРАЖЕНИЯ ССЫЛОК")
    print("=" * 80)

    print("\n📊 Тестовые данные с длинными ссылками:")
    print("-" * 50)

    for i, supplier in enumerate(test_suppliers, 1):
        print(f"\n{i}. Компания: {supplier['name']}")
        print(f"   Телефон: {supplier['phone']}")
        print(f"   Email: {supplier['email']}")
        print(f"   Сайт: {supplier['website']}")
        print(f"   Тип: {supplier['company_type']}")
        print(f"   Релевантность: {supplier['relevance_score']}")

    print("\n" + "=" * 80)
    print("✅ ПРОВЕРКА В БРАУЗЕРЕ")
    print("=" * 80)
    print("1. Запустите приложение: python web_app.py")
    print("2. Откройте: http://localhost:5000")
    print("3. Выполните поиск")
    print("4. Проверьте отображение ссылок в результатах")
    print("\nОжидаемый результат:")
    print("✓ Длинные ссылки должны быть усечены многоточием")
    print("✓ При наведении курсора должен показываться полный URL")
    print("✓ Ссылки должны быть кликабельными")
    print("✓ Кнопка копирования должна работать")
    print("=" * 80)

if __name__ == "__main__":
    test_link_display()
