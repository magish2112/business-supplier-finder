#!/usr/bin/env python3
"""
Улучшенная версия парсера с лучшим извлечением контактов
"""

import requests
import time
import re
from typing import List, Optional
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import PARSER_CONFIG, CATEGORIES
from models import Company, SearchResult
from datetime import datetime

class ImprovedCompanyParser:
    """Улучшенный парсер для поиска компаний"""
    
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
            
    def search_avito_improved(self, query: str, category: str) -> List[Company]:
        """Улучшенный поиск на Avito"""
        companies = []
        try:
            search_url = f"https://www.avito.ru/all?q={query}+строительные+материалы"
            
            if not self.driver:
                self.setup_driver()
                
            self.driver.get(search_url)
            time.sleep(PARSER_CONFIG['delay_between_requests'])
            
            # Парсинг результатов
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = soup.find_all('div', {'data-marker': 'item'})
            
            print(f"Найдено элементов на Avito: {len(items)}")
            
            for item in items[:15]:  # Увеличиваем лимит
                try:
                    # Ищем заголовок
                    title = self._extract_title_avito(item)
                    if not title:
                        continue
                    
                    # Извлекаем контакты
                    phone = self._extract_phone_improved(item)
                    email = self._extract_email_improved(item)
                    address = self._extract_address_improved(item)
                    website = self._extract_website_improved(item)
                    
                    # Фильтруем только релевантные компании
                    if self._is_relevant_company(title, query):
                        company = Company(
                            name=title,
                            category=category,
                            subcategory=self._determine_subcategory(title, category),
                            address=address,
                            phone=phone,
                            email=email,
                            website=website,
                            source='Avito'
                        )
                        companies.append(company)
                        print(f"✅ Добавлена компания: {title}")
                        if phone:
                            print(f"   📞 Телефон: {phone}")
                    
                except Exception as e:
                    print(f"Ошибка при парсинге элемента Avito: {e}")
                    
        except Exception as e:
            print(f"Ошибка при поиске на Avito: {e}")
            
        return companies
    
    def _extract_title_avito(self, item) -> Optional[str]:
        """Извлечение заголовка с Avito"""
        # Попробуем найти заголовок в ссылке
        title_link = item.find('a', {'data-marker': 'item-title'})
        if title_link:
            return title_link.get_text(strip=True)
        
        # Ищем в других местах
        title_selectors = [
            'h3[itemprop="name"]',
            '.iva-item-title',
            '.item-title',
            'h3',
            'a[class*="title"]',
            'span[class*="title"]'
        ]
        
        for selector in title_selectors:
            title_elem = item.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 3:
                    return title
        
        return None
    
    def _extract_phone_improved(self, element) -> Optional[str]:
        """Улучшенное извлечение телефона"""
        # Паттерны для телефонов
        phone_patterns = [
            r'(\+7|8)[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{2})[\s\-\(\)]*(\d{2})',
            r'(\+7|8)[\s\-\(\)]*(\d{4})[\s\-\(\)]*(\d{2})[\s\-\(\)]*(\d{2})[\s\-\(\)]*(\d{2})',
            r'(\d{3})[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{2})[\s\-\(\)]*(\d{2})'
        ]
        
        text = element.get_text()
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, text)
            if phone_match:
                phone = phone_match.group(0)
                # Очищаем телефон
                phone = re.sub(r'[^\d+]', '', phone)
                if len(phone) >= 10:
                    return phone
        
        return None
    
    def _extract_email_improved(self, element) -> Optional[str]:
        """Улучшенное извлечение email"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        text = element.get_text()
        email_match = re.search(email_pattern, text)
        
        if email_match:
            return email_match.group(0)
        return None
    
    def _extract_website_improved(self, element) -> Optional[str]:
        """Улучшенное извлечение сайта"""
        website_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
        
        text = element.get_text()
        website_match = re.search(website_pattern, text)
        
        if website_match:
            return website_match.group(0)
        return None
    
    def _extract_address_improved(self, element) -> Optional[str]:
        """Улучшенное извлечение адреса"""
        # Ищем адрес в различных элементах
        address_selectors = [
            'span[class*="address"]',
            'div[class*="address"]',
            'span[class*="location"]',
            'div[class*="location"]',
            'span[class*="geo"]',
            'div[class*="geo"]'
        ]
        
        for selector in address_selectors:
            address_elem = element.select_one(selector)
            if address_elem:
                address = address_elem.get_text(strip=True)
                if address and len(address) > 5:
                    return address
        
        # Ищем по ключевым словам
        text = element.get_text()
        address_keywords = ['ул.', 'улица', 'проспект', 'пр.', 'дом', 'д.', 'кв.', 'офис', 'район', 'область']
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if any(keyword in line.lower() for keyword in address_keywords):
                if len(line) > 10 and len(line) < 200:
                    return line
        
        return None
    
    def _is_relevant_company(self, title: str, query: str) -> bool:
        """Проверка релевантности компании"""
        title_lower = title.lower()
        query_lower = query.lower()
        
        # Ключевые слова для строительных материалов
        relevant_keywords = [
            'металлопрокат', 'арматура', 'труба', 'лист', 'уголок', 'швеллер',
            'строительные', 'материалы', 'строй', 'металл', 'профиль',
            'ооо', 'зао', 'ип', 'компания', 'фирма', 'группа', 'торг'
        ]
        
        # Проверяем наличие ключевых слов
        has_relevant_keywords = any(keyword in title_lower for keyword in relevant_keywords)
        
        # Проверяем соответствие запросу
        matches_query = query_lower in title_lower
        
        return has_relevant_keywords or matches_query
    
    def _determine_subcategory(self, name: str, category: str) -> str:
        """Определение подкатегории на основе названия"""
        name_lower = name.lower()
        
        if category in CATEGORIES:
            for subcategory in CATEGORIES[category]['subcategories']:
                if subcategory.lower() in name_lower:
                    return subcategory
                    
        return CATEGORIES[category]['subcategories'][0] if category in CATEGORIES else 'Другое'
    
    def search_all_sources_improved(self, query: str, category: str) -> SearchResult:
        """Улучшенный поиск по всем источникам"""
        all_companies = []
        
        # Поиск на Avito
        print(f"🔍 Поиск на Avito: {query}")
        avito_companies = self.search_avito_improved(query, category)
        all_companies.extend(avito_companies)
        
        print(f"✅ Найдено на Avito: {len(avito_companies)} компаний")
        
        return SearchResult(
            companies=all_companies,
            total_found=len(all_companies),
            search_query=query,
            source='all',
            timestamp=datetime.now()
        )
    
    def __del__(self):
        """Деструктор для закрытия драйвера"""
        self.close_driver()

def test_improved_parser():
    """Тест улучшенного парсера"""
    print("🧪 Тест улучшенного парсера")
    print("=" * 50)
    
    parser = ImprovedCompanyParser()
    
    try:
        # Тестируем разные запросы
        queries = ["металлопрокат", "арматура", "трубы профильные"]
        
        all_companies = []
        
        for query in queries:
            print(f"\n🔍 Поиск: {query}")
            result = parser.search_all_sources_improved(query, "Металлопрокат")
            all_companies.extend(result.companies)
            print(f"Найдено: {len(result.companies)} компаний")
        
        # Удаляем дубликаты
        unique_companies = []
        seen_names = set()
        
        for company in all_companies:
            normalized_name = company.name.lower().strip()
            if normalized_name not in seen_names:
                seen_names.add(normalized_name)
                unique_companies.append(company)
        
        print(f"\n📊 Итоговые результаты:")
        print(f"Всего найдено: {len(all_companies)} компаний")
        print(f"Уникальных: {len(unique_companies)} компаний")
        
        if unique_companies:
            print("\n🏢 Найденные компании:")
            for i, company in enumerate(unique_companies[:10], 1):
                print(f"{i}. {company.name}")
                if company.phone:
                    print(f"   📞 {company.phone}")
                if company.address:
                    print(f"   📍 {company.address[:50]}...")
                print()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        parser.close_driver()

if __name__ == "__main__":
    test_improved_parser() 