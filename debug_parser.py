#!/usr/bin/env python3
"""
Отладочная версия парсера для диагностики проблем
"""

import requests
import time
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_avito_parsing():
    """Тест парсинга Avito"""
    print("🔍 Тестирование парсинга Avito...")
    
    try:
        # Настройка драйвера
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Поиск по металлопрокату
        search_url = "https://www.avito.ru/all?q=металлопрокат+строительные+материалы"
        print(f"Переход на: {search_url}")
        
        driver.get(search_url)
        time.sleep(5)  # Ждем загрузки
        
        # Сохраняем HTML для анализа
        with open("avito_debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("✅ HTML сохранен в avito_debug.html")
        
        # Парсим результаты
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Ищем различные селекторы
        selectors_to_try = [
            'div[data-marker="item"]',
            '.iva-item-root',
            '.iva-item',
            '.item',
            '[data-marker]',
            'div[class*="item"]',
            'div[class*="listing"]'
        ]
        
        for selector in selectors_to_try:
            items = soup.select(selector)
            print(f"Селектор '{selector}': найдено {len(items)} элементов")
            
            if items:
                print(f"✅ Найден рабочий селектор: {selector}")
                break
        
        # Пробуем найти названия компаний
        title_selectors = [
            'h3[itemprop="name"]',
            '.iva-item-title',
            '.item-title',
            'h3',
            'a[class*="title"]',
            'span[class*="title"]'
        ]
        
        for selector in title_selectors:
            titles = soup.select(selector)
            print(f"Заголовки '{selector}': найдено {len(titles)} элементов")
            
            if titles:
                for i, title in enumerate(titles[:3]):
                    text = title.get_text(strip=True)
                    if text:
                        print(f"  {i+1}. {text[:50]}...")
        
        driver.quit()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при парсинге Avito: {e}")
        return False

def test_yandex_parsing():
    """Тест парсинга Яндекс.Карт"""
    print("\n🔍 Тестирование парсинга Яндекс.Карт...")
    
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        search_url = "https://yandex.ru/maps/?text=металлопрокат+строительные+материалы"
        print(f"Переход на: {search_url}")
        
        driver.get(search_url)
        time.sleep(5)
        
        # Сохраняем HTML
        with open("yandex_debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("✅ HTML сохранен в yandex_debug.html")
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Ищем селекторы
        selectors_to_try = [
            '.search-result',
            '.business-name',
            '.org-name',
            '[class*="search"]',
            '[class*="business"]',
            '[class*="org"]'
        ]
        
        for selector in selectors_to_try:
            items = soup.select(selector)
            print(f"Селектор '{selector}': найдено {len(items)} элементов")
            
            if items:
                print(f"✅ Найден рабочий селектор: {selector}")
                break
        
        driver.quit()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при парсинге Яндекс.Карт: {e}")
        return False

def test_simple_search():
    """Простой тест поиска"""
    print("\n🔍 Простой тест поиска...")
    
    try:
        # Используем requests для простого поиска
        ua = UserAgent()
        session = requests.Session()
        session.headers.update({
            'User-Agent': ua.random
        })
        
        # Тестируем поиск на разных сайтах
        test_urls = [
            "https://www.avito.ru/all?q=металлопрокат",
            "https://www.avito.ru/all?q=арматура",
            "https://www.avito.ru/all?q=трубы+строительные"
        ]
        
        for url in test_urls:
            print(f"Тестируем: {url}")
            response = session.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Статус: {response.status_code}")
                
                # Ищем ключевые слова в HTML
                content = response.text.lower()
                keywords = ['металлопрокат', 'арматура', 'труба', 'строительные', 'материалы']
                
                found_keywords = [kw for kw in keywords if kw in content]
                print(f"Найдены ключевые слова: {found_keywords}")
                
                # Ищем телефоны
                import re
                phone_pattern = r'(\+7|8)[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{2})[\s\-\(\)]*(\d{2})'
                phones = re.findall(phone_pattern, response.text)
                print(f"Найдено телефонов: {len(phones)}")
                
            else:
                print(f"❌ Статус: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Ошибка при простом поиске: {e}")
        return False
    
    return True

def main():
    """Главная функция отладки"""
    print("🐛 Отладка парсера поставщиков")
    print("=" * 50)
    
    tests = [
        test_simple_search,
        test_avito_parsing,
        test_yandex_parsing
    ]
    
    for test in tests:
        test()
        print()

if __name__ == "__main__":
    main() 