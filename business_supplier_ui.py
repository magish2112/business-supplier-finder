#!/usr/bin/env python3
"""
Интерфейс для поиска бизнес-поставщиков
"""

from business_supplier_finder import BusinessSupplierFinder
import json
from datetime import datetime

class BusinessSupplierUI:
    """Интерфейс для поиска бизнес-поставщиков"""
    
    def __init__(self):
        self.finder = BusinessSupplierFinder()
        
    def run(self):
        """Запуск интерфейса"""
        print("🏢 Поиск бизнес-поставщиков строительных материалов")
        print("=" * 60)
        print("Специализированный поиск крупных компаний с безналичной оплатой")
        print("=" * 60)
        
        while True:
            print("\nВыберите действие:")
            print("1. Поиск бизнес-поставщика")
            print("2. Быстрый поиск")
            print("3. Сохраненные запросы")
            print("4. Экспорт результатов")
            print("0. Выход")
            
            choice = input("\nВведите номер: ").strip()
            
            if choice == "0":
                print("До свидания!")
                break
            elif choice == "1":
                self.search_business_supplier()
            elif choice == "2":
                self.quick_search()
            elif choice == "3":
                self.show_saved_searches()
            elif choice == "4":
                self.export_results()
            else:
                print("Неверный выбор. Попробуйте снова.")
    
    def search_business_supplier(self):
        """Поиск бизнес-поставщика"""
        print("\n🔍 Поиск бизнес-поставщика")
        print("-" * 40)
        
        # Ввод данных
        product = input("Введите название товара: ").strip()
        if not product:
            print("❌ Название товара обязательно!")
            return
        
        region = input("Введите регион (например, Ставрополь): ").strip()
        if not region:
            print("❌ Регион обязателен!")
            return
        
        quantity = input("Введите количество (необязательно): ").strip()
        
        # Дополнительные параметры
        print("\nДополнительные параметры:")
        min_price = input("Минимальная цена (необязательно): ").strip()
        max_price = input("Максимальная цена (необязательно): ").strip()
        delivery_needed = input("Нужна доставка? (да/нет): ").strip().lower() == 'да'
        payment_type = input("Тип оплаты (безнал/наличные/оба): ").strip().lower()
        
        print(f"\n🔍 Поиск бизнес-поставщиков для: {product}")
        print(f"📍 Регион: {region}")
        print(f"📦 Количество: {quantity}")
        print(f"💰 Цена: {min_price or 'не указано'} - {max_price or 'не указано'}")
        print(f"🚚 Доставка: {'Да' if delivery_needed else 'Нет'}")
        print(f"💳 Оплата: {payment_type}")
        print("=" * 60)
        
        # Поиск
        try:
            suppliers = self.finder.search_suppliers(product, region, quantity)
            
            if suppliers:
                print(f"\n✅ Найдено бизнес-поставщиков: {len(suppliers)}")
                self.display_business_suppliers(suppliers)
                
                # Сохраняем результаты
                self.save_search_results(product, region, quantity, suppliers)
                
                # Предлагаем экспорт
                export_choice = input("\nЭкспортировать результаты в файл? (да/нет): ").strip().lower()
                if export_choice == 'да':
                    self.export_to_file(suppliers, product, region)
            else:
                print("❌ Бизнес-поставщики не найдены")
                print("Попробуйте изменить параметры поиска")
                
        except Exception as e:
            print(f"❌ Ошибка при поиске: {e}")
    
    def quick_search(self):
        """Быстрый поиск"""
        print("\n⚡ Быстрый поиск")
        print("-" * 40)
        
        # Предустановленные запросы
        quick_searches = [
            {
                'name': 'Grohe дистрибьютор',
                'product': 'Grohe',
                'region': 'Ставрополь',
                'quantity': 'опт'
            },
            {
                'name': 'Металлопрокат оптовый поставщик',
                'product': 'металлопрокат',
                'region': 'Ставрополь',
                'quantity': 'опт'
            },
            {
                'name': 'Сантехника оптовая компания',
                'product': 'сантехника',
                'region': 'Ставрополь',
                'quantity': 'опт'
            }
        ]
        
        print("Выберите быстрый поиск:")
        for i, search in enumerate(quick_searches, 1):
            print(f"{i}. {search['name']}")
        
        try:
            choice = int(input("\nВведите номер: ")) - 1
            if 0 <= choice < len(quick_searches):
                selected_search = quick_searches[choice]
                
                print(f"\n🔍 Быстрый поиск: {selected_search['name']}")
                print("=" * 40)
                
                suppliers = self.finder.search_suppliers(
                    selected_search['product'],
                    selected_search['region'],
                    selected_search['quantity']
                )
                
                if suppliers:
                    print(f"\n✅ Найдено: {len(suppliers)} поставщиков")
                    self.display_business_suppliers(suppliers[:5])  # Показываем только первые 5
                else:
                    print("❌ Поставщики не найдены")
            else:
                print("Неверный номер")
        except ValueError:
            print("Введите корректный номер")
    
    def display_business_suppliers(self, suppliers):
        """Отображение бизнес-поставщиков"""
        print("\n🏢 Найденные бизнес-поставщики:")
        print("=" * 60)
        
        for i, supplier in enumerate(suppliers, 1):
            print(f"\n{i}. {supplier['name']}")
            print(f"   📞 Телефон: {supplier.get('phone', 'Не указан')}")
            print(f"   📧 Email: {supplier.get('email', 'Не указан')}")
            print(f"   🌐 Сайт: {supplier.get('website', 'Не указан')}")
            print(f"   📊 Релевантность: {supplier.get('relevance_score', 0)}")
            print(f"   🏢 Бизнес-поставщик: {'Да' if supplier.get('is_business') else 'Нет'}")
            print(f"   📋 Источник: {supplier.get('source', 'Неизвестно')}")
            
            if supplier.get('description'):
                desc = supplier['description'][:100] + "..." if len(supplier['description']) > 100 else supplier['description']
                print(f"   📝 Описание: {desc}")
            
            if i >= 10:  # Показываем только первые 10
                print(f"\n... и еще {len(suppliers) - 10} поставщиков")
                break
    
    def save_search_results(self, product, region, quantity, suppliers):
        """Сохранение результатов поиска"""
        try:
            search_data = {
                'timestamp': datetime.now().isoformat(),
                'product': product,
                'region': region,
                'quantity': quantity,
                'suppliers_count': len(suppliers),
                'suppliers': suppliers
            }
            
            # Сохраняем в JSON файл
            filename = f"business_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(search_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Результаты сохранены в {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при сохранении: {e}")
    
    def export_to_file(self, suppliers, product, region):
        """Экспорт в файл"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"business_suppliers_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Поиск бизнес-поставщиков\n")
                f.write(f"Товар: {product}\n")
                f.write(f"Регион: {region}\n")
                f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                
                for i, supplier in enumerate(suppliers, 1):
                    f.write(f"{i}. {supplier['name']}\n")
                    f.write(f"   Телефон: {supplier.get('phone', 'Не указан')}\n")
                    f.write(f"   Email: {supplier.get('email', 'Не указан')}\n")
                    f.write(f"   Сайт: {supplier.get('website', 'Не указан')}\n")
                    f.write(f"   Релевантность: {supplier.get('relevance_score', 0)}\n")
                    f.write(f"   Бизнес-поставщик: {'Да' if supplier.get('is_business') else 'Нет'}\n")
                    f.write(f"   Источник: {supplier.get('source', 'Неизвестно')}\n")
                    if supplier.get('description'):
                        f.write(f"   Описание: {supplier['description']}\n")
                    f.write("\n")
            
            print(f"✅ Результаты экспортированы в {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при экспорте: {e}")
    
    def show_saved_searches(self):
        """Показать сохраненные поиски"""
        print("\n📋 Сохраненные поиски")
        print("-" * 40)
        
        import glob
        import os
        
        json_files = glob.glob("business_search_*.json")
        
        if not json_files:
            print("Сохраненных поисков не найдено")
            return
        
        print(f"Найдено сохраненных поисков: {len(json_files)}")
        
        for i, filename in enumerate(json_files[:5], 1):  # Показываем только последние 5
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                print(f"\n{i}. {data['product']}")
                print(f"   📍 Регион: {data['region']}")
                print(f"   📦 Количество: {data['quantity']}")
                print(f"   🏢 Найдено поставщиков: {data['suppliers_count']}")
                print(f"   📅 Дата: {data['timestamp'][:19]}")
                
            except Exception as e:
                print(f"Ошибка чтения файла {filename}: {e}")
    
    def export_results(self):
        """Экспорт результатов"""
        print("\n📤 Экспорт результатов")
        print("-" * 40)
        
        import glob
        
        json_files = glob.glob("business_search_*.json")
        
        if not json_files:
            print("Файлов для экспорта не найдено")
            return
        
        print("Доступные файлы для экспорта:")
        for i, filename in enumerate(json_files, 1):
            print(f"{i}. {filename}")
        
        try:
            choice = int(input("\nВыберите номер файла: ")) - 1
            if 0 <= choice < len(json_files):
                filename = json_files[choice]
                self.export_specific_file(filename)
            else:
                print("Неверный номер файла")
        except ValueError:
            print("Введите корректный номер")
    
    def export_specific_file(self, filename):
        """Экспорт конкретного файла"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            export_filename = f"business_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(export_filename, 'w', encoding='utf-8') as f:
                f.write(f"Экспорт результатов поиска бизнес-поставщиков\n")
                f.write(f"Товар: {data['product']}\n")
                f.write(f"Регион: {data['region']}\n")
                f.write(f"Количество: {data['quantity']}\n")
                f.write(f"Дата поиска: {data['timestamp'][:19]}\n")
                f.write("=" * 60 + "\n\n")
                
                for supplier in data['suppliers']:
                    f.write(f"🏢 {supplier['name']}\n")
                    f.write(f"📞 {supplier.get('phone', 'Не указан')}\n")
                    f.write(f"📧 {supplier.get('email', 'Не указан')}\n")
                    f.write(f"🌐 {supplier.get('website', 'Не указан')}\n")
                    f.write(f"📊 Релевантность: {supplier.get('relevance_score', 0)}\n")
                    f.write(f"🏢 Бизнес-поставщик: {'Да' if supplier.get('is_business') else 'Нет'}\n")
                    f.write(f"📋 Источник: {supplier.get('source', 'Неизвестно')}\n")
                    if supplier.get('description'):
                        f.write(f"📝 Описание: {supplier['description']}\n")
                    f.write("\n")
            
            print(f"✅ Результаты экспортированы в {export_filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при экспорте: {e}")

def main():
    """Главная функция"""
    ui = BusinessSupplierUI()
    ui.run()

if __name__ == "__main__":
    main() 