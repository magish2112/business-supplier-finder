#!/usr/bin/env python3
"""
Парсер для поиска крупных поставщиков строительных материалов
Специализируется на поиске компаний с безналичной оплатой
"""

import requests
import time
import re
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

class SupplierFinder:
    """Поисковик поставщиков"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.ua.random
        })
        self.driver = None
        
    def setup_driver(self):
        """Настройка Selenium WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument(f'--user-agent={self.ua.random}')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
    def close_driver(self):
        """Закрытие драйвера"""
        if self.driver:
            self.driver.quit()
    
    def search_suppliers(self, product: str, region: str, quantity: str = "") -> List[Dict]:
        """Поиск поставщиков по товару и региону"""
        suppliers = []
        
        # Формируем поисковые запросы
        search_queries = self._generate_search_queries(product, region)
        
        print(f"🔍 Поиск поставщиков для: {product}")
        print(f"📍 Регион: {region}")
        print(f"📦 Количество: {quantity}")
        print("=" * 60)
        
        for query in search_queries:
            print(f"\nПоиск по запросу: {query}")
            
            # Поиск на разных площадках
            avito_results = self._search_avito_suppliers(query, region)
            suppliers.extend(avito_results)
            
            # Поиск в Яндекс.Картах
            yandex_results = self._search_yandex_suppliers(query, region)
            suppliers.extend(yandex_results)
            
            # Поиск на специализированных сайтах
            specialized_results = self._search_specialized_sites(query, region)
            suppliers.extend(specialized_results)
            
            time.sleep(2)  # Задержка между запросами
        
        # Фильтруем и ранжируем результаты
        filtered_suppliers = self._filter_and_rank_suppliers(suppliers, product, region)
        
        return filtered_suppliers
    
    def _generate_search_queries(self, product: str, region: str) -> List[str]:
        """Генерация поисковых запросов"""
        queries = []
        
        # Основной запрос
        queries.append(f"{product} {region}")
        
        # Запросы с ключевыми словами для оптовиков
        wholesale_keywords = ["опт", "оптовый", "склад", "база", "компания", "поставщик"]
        for keyword in wholesale_keywords:
            queries.append(f"{product} {keyword} {region}")
        
        # Запросы с брендами (если есть)
        brand_keywords = ["grohe", "hansgrohe", "villeroy", "duravit", "geberit"]
        for brand in brand_keywords:
            if brand.lower() in product.lower():
                queries.append(f"{brand} {region} опт")
        
        return queries
    
    def _search_avito_suppliers(self, query: str, region: str) -> List[Dict]:
        """Поиск поставщиков на Avito"""
        suppliers = []
        
        try:
            if not self.driver:
                self.setup_driver()
            
            search_url = f"https://www.avito.ru/all?q={query}&location={region}"
            self.driver.get(search_url)
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = soup.find_all('div', {'data-marker': 'item'})
            
            print(f"Найдено объявлений на Avito: {len(items)}")
            
            for item in items[:10]:
                try:
                    supplier = self._extract_avito_supplier(item, query)
                    if supplier:
                        suppliers.append(supplier)
                        
                except Exception as e:
                    print(f"Ошибка при парсинге Avito: {e}")
                    
        except Exception as e:
            print(f"Ошибка при поиске на Avito: {e}")
            
        return suppliers
    
    def _extract_avito_supplier(self, item, query: str) -> Optional[Dict]:
        """Извлечение данных поставщика с Avito"""
        try:
            # Название компании
            title_elem = item.find('a', {'data-marker': 'item-title'})
            if not title_elem:
                return None
                
            title = title_elem.get_text(strip=True)
            
            # Проверяем релевантность
            if not self._is_relevant_supplier(title, query):
                return None
            
            # Контакты
            phone = self._extract_phone(item)
            email = self._extract_email(item)
            
            # Адрес
            address = self._extract_address(item)
            
            # Проверяем признаки оптовика
            is_wholesale = self._check_wholesale_signs(title, item.get_text())
            
            supplier = {
                'name': title,
                'phone': phone,
                'email': email,
                'address': address,
                'source': 'Avito',
                'is_wholesale': is_wholesale,
                'relevance_score': self._calculate_relevance(title, query)
            }
            
            return supplier
            
        except Exception as e:
            print(f"Ошибка извлечения данных: {e}")
            return None
    
    def _search_yandex_suppliers(self, query: str, region: str) -> List[Dict]:
        """Поиск поставщиков в Яндекс.Картах"""
        suppliers = []
        
        try:
            if not self.driver:
                self.setup_driver()
            
            search_url = f"https://yandex.ru/maps/?text={query}+{region}"
            self.driver.get(search_url)
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = soup.find_all('div', class_=lambda x: x and 'search' in x)
            
            print(f"Найдено компаний в Яндекс.Картах: {len(items)}")
            
            for item in items[:10]:
                try:
                    supplier = self._extract_yandex_supplier(item, query)
                    if supplier:
                        suppliers.append(supplier)
                        
                except Exception as e:
                    print(f"Ошибка при парсинге Яндекс.Карт: {e}")
                    
        except Exception as e:
            print(f"Ошибка при поиске в Яндекс.Картах: {e}")
            
        return suppliers
    
    def _extract_yandex_supplier(self, item, query: str) -> Optional[Dict]:
        """Извлечение данных поставщика с Яндекс.Карт"""
        try:
            # Ищем название компании
            name = None
            name_selectors = [
                'span[class*="business"]',
                'span[class*="org"]',
                'div[class*="business"]',
                'div[class*="org"]'
            ]
            
            for selector in name_selectors:
                name_elem = item.select_one(selector)
                if name_elem:
                    name = name_elem.get_text(strip=True)
                    break
            
            if not name:
                return None
            
            # Проверяем релевантность
            if not self._is_relevant_supplier(name, query):
                return None
            
            # Контакты
            phone = self._extract_phone(item)
            website = self._extract_website(item)
            address = self._extract_address(item)
            
            # Проверяем признаки оптовика
            is_wholesale = self._check_wholesale_signs(name, item.get_text())
            
            supplier = {
                'name': name,
                'phone': phone,
                'website': website,
                'address': address,
                'source': 'Yandex Maps',
                'is_wholesale': is_wholesale,
                'relevance_score': self._calculate_relevance(name, query)
            }
            
            return supplier
            
        except Exception as e:
            print(f"Ошибка извлечения данных: {e}")
            return None
    
    def _search_specialized_sites(self, query: str, region: str) -> List[Dict]:
        """Поиск на специализированных сайтах"""
        suppliers = []
        
        # Список специализированных сайтов
        specialized_sites = [
            "https://www.ruslist.ru",
            "https://www.yp.ru",
            "https://www.2gis.ru"
        ]
        
        for site in specialized_sites:
            try:
                print(f"Поиск на {site}")
                # Здесь можно добавить специфичную логику для каждого сайта
                # Пока возвращаем пустой список
                pass
            except Exception as e:
                print(f"Ошибка при поиске на {site}: {e}")
        
        return suppliers
    
    def _is_relevant_supplier(self, name: str, query: str) -> bool:
        """Проверка релевантности поставщика"""
        name_lower = name.lower()
        query_lower = query.lower()
        
        # Ключевые слова для оптовиков
        wholesale_keywords = [
            'ооо', 'зао', 'ип', 'компания', 'фирма', 'группа', 'торг',
            'опт', 'оптовый', 'склад', 'база', 'поставщик', 'дистрибьютор',
            'металл', 'строй', 'сантехника', 'электро', 'инструмент'
        ]
        
        # Проверяем наличие ключевых слов
        has_wholesale_keywords = any(keyword in name_lower for keyword in wholesale_keywords)
        
        # Проверяем соответствие запросу
        matches_query = any(word in name_lower for word in query_lower.split())
        
        return has_wholesale_keywords or matches_query
    
    def _check_wholesale_signs(self, name: str, text: str) -> bool:
        """Проверка признаков оптовика"""
        text_lower = text.lower()
        
        wholesale_indicators = [
            'опт', 'оптовый', 'склад', 'база', 'поставщик', 'дистрибьютор',
            'безналичный', 'перечисление', 'счет', 'договор', 'накладная',
            'отгрузка', 'доставка', 'грузоперевозки'
        ]
        
        return any(indicator in text_lower for indicator in wholesale_indicators)
    
    def _calculate_relevance(self, name: str, query: str) -> int:
        """Расчет релевантности"""
        score = 0
        name_lower = name.lower()
        query_lower = query.lower()
        
        # Бонус за точное совпадение
        if query_lower in name_lower:
            score += 10
        
        # Бонус за ключевые слова оптовика
        wholesale_keywords = ['опт', 'склад', 'база', 'поставщик']
        for keyword in wholesale_keywords:
            if keyword in name_lower:
                score += 5
        
        # Бонус за наличие контактов
        if self._extract_phone({'text': name}):
            score += 3
        
        return score
    
    def _filter_and_rank_suppliers(self, suppliers: List[Dict], product: str, region: str) -> List[Dict]:
        """Фильтрация и ранжирование поставщиков"""
        # Удаляем дубликаты
        unique_suppliers = []
        seen_names = set()
        
        for supplier in suppliers:
            normalized_name = supplier['name'].lower().strip()
            if normalized_name not in seen_names:
                seen_names.add(normalized_name)
                unique_suppliers.append(supplier)
        
        # Сортируем по релевантности
        unique_suppliers.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Фильтруем только оптовиков
        wholesale_suppliers = [s for s in unique_suppliers if s.get('is_wholesale', False)]
        
        print(f"\n📊 Результаты поиска:")
        print(f"Всего найдено: {len(suppliers)}")
        print(f"Уникальных: {len(unique_suppliers)}")
        print(f"Оптовиков: {len(wholesale_suppliers)}")
        
        return wholesale_suppliers if wholesale_suppliers else unique_suppliers
    
    def _extract_phone(self, element) -> Optional[str]:
        """Извлечение телефона"""
        phone_pattern = r'(\+7|8)[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{2})[\s\-\(\)]*(\d{2})'
        
        if isinstance(element, dict):
            text = element.get('text', '')
        else:
            text = element.get_text()
        
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            return phone_match.group(0)
        return None
    
    def _extract_email(self, element) -> Optional[str]:
        """Извлечение email"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        text = element.get_text()
        email_match = re.search(email_pattern, text)
        
        if email_match:
            return email_match.group(0)
        return None
    
    def _extract_website(self, element) -> Optional[str]:
        """Извлечение сайта"""
        website_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
        
        text = element.get_text()
        website_match = re.search(website_pattern, text)
        
        if website_match:
            return website_match.group(0)
        return None
    
    def _extract_address(self, element) -> Optional[str]:
        """Извлечение адреса"""
        address_selectors = [
            'span[class*="address"]',
            'div[class*="address"]',
            'span[class*="location"]',
            'div[class*="location"]'
        ]
        
        for selector in address_selectors:
            address_elem = element.select_one(selector)
            if address_elem:
                return address_elem.get_text(strip=True)
        
        return None
    
    def __del__(self):
        """Деструктор"""
        self.close_driver()

def test_supplier_finder():
    """Тест поисковика поставщиков"""
    print("🧪 Тест поисковика поставщиков")
    print("=" * 60)
    
    finder = SupplierFinder()
    
    # Тестовые запросы
    test_cases = [
        {
            'product': 'Душевой гарнитур Grohe New Tempesta 110 27853003',
            'region': 'Ставрополь',
            'quantity': '25 штук'
        },
        {
            'product': 'уголок оцинкованный 70*70*8 L=6000',
            'region': 'Ставрополь',
            'quantity': '24 метра'
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n🔍 Тест {i}: {case['product']}")
        print(f"📍 Регион: {case['region']}")
        print(f"📦 Количество: {case['quantity']}")
        print("-" * 50)
        
        suppliers = finder.search_suppliers(
            case['product'], 
            case['region'], 
            case['quantity']
        )
        
        if suppliers:
            print(f"\n✅ Найдено поставщиков: {len(suppliers)}")
            for j, supplier in enumerate(suppliers[:5], 1):
                print(f"\n{j}. {supplier['name']}")
                print(f"   📞 Телефон: {supplier.get('phone', 'Не указан')}")
                print(f"   📧 Email: {supplier.get('email', 'Не указан')}")
                print(f"   🌐 Сайт: {supplier.get('website', 'Не указан')}")
                print(f"   📍 Адрес: {supplier.get('address', 'Не указан')}")
                print(f"   📊 Релевантность: {supplier.get('relevance_score', 0)}")
                print(f"   🏢 Оптовик: {'Да' if supplier.get('is_wholesale') else 'Нет'}")
        else:
            print("❌ Поставщики не найдены")
    
    finder.close_driver()

if __name__ == "__main__":
    test_supplier_finder() 