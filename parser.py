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

class CompanyParser:
    """Парсер для поиска компаний"""
    
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
            
    def search_avito(self, query: str, category: str) -> List[Company]:
        """Поиск на Avito"""
        companies = []
        try:
            # Поиск по строительным материалам на Avito
            search_url = f"https://www.avito.ru/all?q={query}+строительные+материалы"
            
            if not self.driver:
                self.setup_driver()
                
            self.driver.get(search_url)
            time.sleep(PARSER_CONFIG['delay_between_requests'])
            
            # Парсинг результатов
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Используем правильный селектор на основе отладки
            items = soup.find_all('div', {'data-marker': 'item'})
            
            print(f"Найдено элементов на Avito: {len(items)}")
            
            for item in items[:10]:  # Ограничиваем первыми 10 результатами
                try:
                    # Ищем заголовок в различных местах
                    title = None
                    
                    # Попробуем найти заголовок в ссылке
                    title_link = item.find('a', {'data-marker': 'item-title'})
                    if title_link:
                        title = title_link.get_text(strip=True)
                    
                    # Если не нашли, ищем в других местах
                    if not title:
                        title_elem = item.find('h3') or item.find('span', class_='title') or item.find('a', class_='title')
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                    
                    # Если все еще нет заголовка, попробуем найти любой текст
                    if not title:
                        # Ищем любой текст, который может быть названием
                        text_elements = item.find_all(['span', 'div', 'a'])
                        for elem in text_elements:
                            text = elem.get_text(strip=True)
                            if text and len(text) > 5 and len(text) < 100:
                                # Проверяем, что это похоже на название компании
                                if any(keyword in text.lower() for keyword in ['ооо', 'зао', 'ип', 'компания', 'фирма', 'группа']):
                                    title = text
                                    break
                    
                    if not title:
                        continue
                        
                    # Извлекаем контакты
                    phone = self._extract_phone(item)
                    email = self._extract_email(item)
                    
                    # Ищем адрес
                    address = self._extract_address(item)
                    
                    company = Company(
                        name=title,
                        category=category,
                        subcategory=self._determine_subcategory(title, category),
                        address=address,
                        phone=phone,
                        email=email,
                        source='Avito'
                    )
                    companies.append(company)
                    print(f"Добавлена компания: {title}")
                    
                except Exception as e:
                    print(f"Ошибка при парсинге элемента Avito: {e}")
                    
        except Exception as e:
            print(f"Ошибка при поиске на Avito: {e}")
            
        return companies
    
    def search_yandex_maps(self, query: str, category: str) -> List[Company]:
        """Поиск в Яндекс.Картах"""
        companies = []
        try:
            search_url = f"https://yandex.ru/maps/?text={query}+строительные+материалы"
            
            if not self.driver:
                self.setup_driver()
                
            self.driver.get(search_url)
            time.sleep(PARSER_CONFIG['delay_between_requests'])
            
            # Ждем загрузки результатов
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "search-result"))
                )
            except:
                print("Не удалось дождаться загрузки результатов Яндекс.Карт")
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Используем более широкий селектор
            items = soup.find_all('div', class_=lambda x: x and 'search' in x)
            
            print(f"Найдено элементов в Яндекс.Картах: {len(items)}")
            
            for item in items[:10]:
                try:
                    # Ищем название компании
                    name = None
                    
                    # Пробуем разные селекторы для названия
                    name_selectors = [
                        'span[class*="business"]',
                        'span[class*="org"]',
                        'div[class*="business"]',
                        'div[class*="org"]',
                        'a[class*="business"]',
                        'a[class*="org"]'
                    ]
                    
                    for selector in name_selectors:
                        name_elem = item.select_one(selector)
                        if name_elem:
                            name = name_elem.get_text(strip=True)
                            break
                    
                    if not name:
                        # Ищем любой текст, который может быть названием
                        text_elements = item.find_all(['span', 'div', 'a'])
                        for elem in text_elements:
                            text = elem.get_text(strip=True)
                            if text and len(text) > 3 and len(text) < 100:
                                # Проверяем, что это похоже на название
                                if any(keyword in text.lower() for keyword in ['ооо', 'зао', 'ип', 'компания', 'фирма', 'группа', 'торг', 'строй']):
                                    name = text
                                    break
                    
                    if not name:
                        continue
                    
                    # Извлекаем адрес и контакты
                    address = self._extract_address(item)
                    phone = self._extract_phone(item)
                    website = self._extract_website(item)
                    
                    company = Company(
                        name=name,
                        category=category,
                        subcategory=self._determine_subcategory(name, category),
                        address=address,
                        phone=phone,
                        website=website,
                        source='Yandex Maps'
                    )
                    companies.append(company)
                    print(f"Добавлена компания: {name}")
                    
                except Exception as e:
                    print(f"Ошибка при парсинге элемента Yandex Maps: {e}")
                    
        except Exception as e:
            print(f"Ошибка при поиске в Yandex Maps: {e}")
            
        return companies
    
    def search_2gis(self, query: str, category: str) -> List[Company]:
        """Поиск в 2GIS"""
        companies = []
        try:
            search_url = f"https://2gis.ru/search/{query}%20строительные%20материалы"
            
            if not self.driver:
                self.setup_driver()
                
            self.driver.get(search_url)
            time.sleep(PARSER_CONFIG['delay_between_requests'])
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Используем более широкий селектор для 2GIS
            items = soup.find_all('div', class_=lambda x: x and ('item' in x or 'result' in x or 'business' in x))
            
            print(f"Найдено элементов в 2GIS: {len(items)}")
            
            for item in items[:10]:
                try:
                    # Ищем название компании
                    name = None
                    
                    # Пробуем разные селекторы
                    name_selectors = [
                        'span[class*="business"]',
                        'span[class*="org"]',
                        'div[class*="business"]',
                        'div[class*="org"]',
                        'a[class*="business"]',
                        'a[class*="org"]'
                    ]
                    
                    for selector in name_selectors:
                        name_elem = item.select_one(selector)
                        if name_elem:
                            name = name_elem.get_text(strip=True)
                            break
                    
                    if not name:
                        # Ищем любой текст, который может быть названием
                        text_elements = item.find_all(['span', 'div', 'a'])
                        for elem in text_elements:
                            text = elem.get_text(strip=True)
                            if text and len(text) > 3 and len(text) < 100:
                                # Проверяем, что это похоже на название
                                if any(keyword in text.lower() for keyword in ['ооо', 'зао', 'ип', 'компания', 'фирма', 'группа', 'торг', 'строй']):
                                    name = text
                                    break
                    
                    if not name:
                        continue
                    
                    # Извлекаем контакты
                    address = self._extract_address(item)
                    phone = self._extract_phone(item)
                    website = self._extract_website(item)
                    
                    company = Company(
                        name=name,
                        category=category,
                        subcategory=self._determine_subcategory(name, category),
                        address=address,
                        phone=phone,
                        website=website,
                        source='2GIS'
                    )
                    companies.append(company)
                    print(f"Добавлена компания: {name}")
                    
                except Exception as e:
                    print(f"Ошибка при парсинге элемента 2GIS: {e}")
                    
        except Exception as e:
            print(f"Ошибка при поиске в 2GIS: {e}")
            
        return companies
    
    def _extract_phone(self, element) -> Optional[str]:
        """Извлечение телефона из элемента"""
        phone_pattern = r'(\+7|8)[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{2})[\s\-\(\)]*(\d{2})'
        
        text = element.get_text()
        phone_match = re.search(phone_pattern, text)
        
        if phone_match:
            return phone_match.group(0)
        return None
    
    def _extract_email(self, element) -> Optional[str]:
        """Извлечение email из элемента"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        text = element.get_text()
        email_match = re.search(email_pattern, text)
        
        if email_match:
            return email_match.group(0)
        return None
    
    def _extract_website(self, element) -> Optional[str]:
        """Извлечение сайта из элемента"""
        website_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
        
        text = element.get_text()
        website_match = re.search(website_pattern, text)
        
        if website_match:
            return website_match.group(0)
        return None
    
    def _extract_address(self, element) -> Optional[str]:
        """Извлечение адреса из элемента"""
        # Ищем адрес в различных элементах
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
        
        # Если не нашли по селекторам, ищем по ключевым словам
        text = element.get_text()
        address_keywords = ['ул.', 'улица', 'проспект', 'пр.', 'дом', 'д.', 'кв.', 'офис']
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if any(keyword in line.lower() for keyword in address_keywords):
                return line
        
        return None
    
    def _determine_subcategory(self, name: str, category: str) -> str:
        """Определение подкатегории на основе названия"""
        name_lower = name.lower()
        
        if category in CATEGORIES:
            for subcategory in CATEGORIES[category]['subcategories']:
                if subcategory.lower() in name_lower:
                    return subcategory
                    
        return CATEGORIES[category]['subcategories'][0] if category in CATEGORIES else 'Другое'
    
    def search_all_sources(self, query: str, category: str) -> SearchResult:
        """Поиск по всем источникам"""
        all_companies = []
        
        # Поиск на Avito
        print(f"Поиск на Avito: {query}")
        avito_companies = self.search_avito(query, category)
        all_companies.extend(avito_companies)
        
        # Поиск в Яндекс.Картах
        print(f"Поиск в Яндекс.Картах: {query}")
        yandex_companies = self.search_yandex_maps(query, category)
        all_companies.extend(yandex_companies)
        
        # Поиск в 2GIS
        print(f"Поиск в 2GIS: {query}")
        gis_companies = self.search_2gis(query, category)
        all_companies.extend(gis_companies)
        
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