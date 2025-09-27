#!/usr/bin/env python3
"""
Простой интерфейс для поиска поставщиков
"""

from supplier_finder import SupplierFinder
import json
from datetime import datetime

class SupplierSearchUI:
    """Интерфейс для поиска поставщиков"""
    
    def __init__(self):
        self.finder = SupplierFinder()
        
    def run(self):
        """Запуск интерфейса"""
        print("🏗️  Поиск поставщиков строительных материалов")
        print("=" * 60)
        print("Специализированный поиск крупных поставщиков с безналичной оплатой")
        print("=" * 60)
        
        while True:
            print("\nВыберите действие:")
            print("1. Поиск поставщика")
            print("2. Сохраненные запросы")
            print("3. Экспорт результатов")
            print("0. Выход")
            
            choice = input("\nВведите номер: ").strip()
            
            if choice == "0":
                print("До свидания!")
                break
            elif choice == "1":
                self.search_supplier()
            elif choice == "2":
                self.show_saved_searches()
            elif choice == "3":
                self.export_results()
            else:
                print("Неверный выбор. Попробуйте снова.")
    
    def search_supplier(self):
        """Поиск поставщика"""
        print("\n🔍 Поиск поставщика")
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
        
        print(f"\n🔍 Поиск поставщиков для: {product}")
        print(f"📍 Регион: {region}")
        print(f"📦 Количество: {quantity}")
        print(f"💰 Цена: {min_price or 'не указано'} - {max_price or 'не указано'}")
        print(f"🚚 Доставка: {'Да' if delivery_needed else 'Нет'}")
        print("=" * 60)
        
        # Поиск
        try:
            suppliers = self.finder.search_suppliers(product, region, quantity)
            
            if suppliers:
                print(f"\n✅ Найдено поставщиков: {len(suppliers)}")
                self.display_suppliers(suppliers)
                
                # Сохраняем результаты
                self.save_search_results(product, region, quantity, suppliers)
                
                # Предлагаем экспорт
                export_choice = input("\nЭкспортировать результаты в файл? (да/нет): ").strip().lower()
                if export_choice == 'да':
                    self.export_to_file(suppliers, product, region)
            else:
                print("❌ Поставщики не найдены")
                print("Попробуйте изменить параметры поиска")
                
        except Exception as e:
            print(f"❌ Ошибка при поиске: {e}")
    
    def display_suppliers(self, suppliers):
        """Отображение поставщиков"""
        print("\n🏢 Найденные поставщики:")
        print("=" * 60)
        
        for i, supplier in enumerate(suppliers, 1):
            print(f"\n{i}. {supplier['name']}")
            print(f"   📞 Телефон: {supplier.get('phone', 'Не указан')}")
            print(f"   📧 Email: {supplier.get('email', 'Не указан')}")
            print(f"   🌐 Сайт: {supplier.get('website', 'Не указан')}")
            print(f"   📍 Адрес: {supplier.get('address', 'Не указан')}")
            print(f"   📊 Релевантность: {supplier.get('relevance_score', 0)}")
            print(f"   🏢 Оптовик: {'Да' if supplier.get('is_wholesale') else 'Нет'}")
            print(f"   📋 Источник: {supplier.get('source', 'Неизвестно')}")
            
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
            filename = f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(search_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Результаты сохранены в {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при сохранении: {e}")
    
    def export_to_file(self, suppliers, product, region):
        """Экспорт в файл"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"suppliers_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Поиск поставщиков\n")
                f.write(f"Товар: {product}\n")
                f.write(f"Регион: {region}\n")
                f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                
                for i, supplier in enumerate(suppliers, 1):
                    f.write(f"{i}. {supplier['name']}\n")
                    f.write(f"   Телефон: {supplier.get('phone', 'Не указан')}\n")
                    f.write(f"   Email: {supplier.get('email', 'Не указан')}\n")
                    f.write(f"   Сайт: {supplier.get('website', 'Не указан')}\n")
                    f.write(f"   Адрес: {supplier.get('address', 'Не указан')}\n")
                    f.write(f"   Релевантность: {supplier.get('relevance_score', 0)}\n")
                    f.write(f"   Оптовик: {'Да' if supplier.get('is_wholesale') else 'Нет'}\n")
                    f.write(f"   Источник: {supplier.get('source', 'Неизвестно')}\n\n")
            
            print(f"✅ Результаты экспортированы в {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при экспорте: {e}")
    
    def show_saved_searches(self):
        """Показать сохраненные поиски"""
        print("\n📋 Сохраненные поиски")
        print("-" * 40)
        
        import glob
        import os
        
        json_files = glob.glob("search_results_*.json")
        
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
        
        json_files = glob.glob("search_results_*.json")
        
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
            
            export_filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(export_filename, 'w', encoding='utf-8') as f:
                f.write(f"Экспорт результатов поиска\n")
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
                    f.write(f"📍 {supplier.get('address', 'Не указан')}\n")
                    f.write(f"📊 Релевантность: {supplier.get('relevance_score', 0)}\n")
                    f.write(f"🏢 Оптовик: {'Да' if supplier.get('is_wholesale') else 'Нет'}\n")
                    f.write(f"📋 Источник: {supplier.get('source', 'Неизвестно')}\n\n")
            
            print(f"✅ Результаты экспортированы в {export_filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при экспорте: {e}")

def main():
    """Главная функция"""
    ui = SupplierSearchUI()
    ui.run()

if __name__ == "__main__":
    main() 