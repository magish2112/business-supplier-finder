#!/usr/bin/env python3
"""
Улучшенный парсер для поиска бизнес-поставщиков через поисковые системы
Специализируется на поиске производителей, дистрибьюторов и крупных поставщиков
"""

import requests
import time
import re
import logging
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import json

from config import PARSER_CONFIG, PERPLEXITY_CONFIG, BUSINESS_KEYWORDS, logger
from models import Company, CompanyType, CompanySize

# Проверяем доступность OpenAI после импорта logger
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI библиотека не установлена. Perplexity API будет недоступен.")
    logger.info("💡 Для улучшения поиска установите: pip install openai")

class BusinessSupplierFinder:
    """Поисковик бизнес-поставщиков"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.ua.random
        })
        self.driver = None

        # Инициализация Perplexity клиента
        self.perplexity_client = None
        if OPENAI_AVAILABLE and PERPLEXITY_CONFIG['enabled'] and PERPLEXITY_CONFIG['api_key']:
            try:
                self.perplexity_client = OpenAI(
                    api_key=PERPLEXITY_CONFIG['api_key'],
                    base_url=PERPLEXITY_CONFIG['base_url']
                )
                logger.info("✅ Perplexity API клиент инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации Perplexity API: {e}")
                self.perplexity_client = None
        else:
            if not PERPLEXITY_CONFIG['enabled']:
                logger.info("ℹ️ Perplexity API отключен в конфигурации")
            elif not PERPLEXITY_CONFIG['api_key']:
                logger.warning("⚠️ Perplexity API ключ не найден. Добавьте PERPLEXITY_API_KEY в .env файл")
            else:
                logger.warning("⚠️ OpenAI библиотека недоступна для Perplexity API")
        
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
    
    def search_suppliers(self, product: str, region: str, quantity: str = "") -> List[Dict[str, Any]]:
        """Поиск поставщиков по товару и региону с улучшенной фильтрацией"""
        suppliers: List[Dict[str, Any]] = []

        # Формируем поисковые запросы для бизнеса
        search_queries = self._generate_business_queries(product, region)

        logger.info(f"🔍 Поиск бизнес-поставщиков для: {product}")
        logger.info(f"📍 Регион: {region}")
        logger.info(f"📦 Количество: {quantity}")
        logger.info(f"📋 Сгенерировано запросов: {len(search_queries)}")

        for query in search_queries:
            logger.info(f"Поиск по запросу: {query}")

            try:
                # Поиск в Google
                google_results = self._search_google_suppliers(query, region)
                suppliers.extend(google_results)
                logger.info(f"Google: найдено {len(google_results)} результатов")

                # Поиск в Яндекс
                yandex_results = self._search_yandex_suppliers(query, region)
                suppliers.extend(yandex_results)
                logger.info(f"Yandex: найдено {len(yandex_results)} результатов")

                # Поиск в специализированных каталогах
                if PARSER_CONFIG['use_business_catalogs']:
                    catalog_results = self._search_business_catalogs(query, region)
                    suppliers.extend(catalog_results)
                    logger.info(f"Каталоги: найдено {len(catalog_results)} результатов")

                # Поиск на сайтах компаний
                if PARSER_CONFIG['use_company_websites']:
                    try:
                        company_results = self._search_company_websites(query, region)
                        suppliers.extend(company_results)
                        logger.info(f"Сайты компаний: найдено {len(company_results)} результатов")
                    except Exception as e:
                        logger.warning(f"Ошибка поиска на сайтах компаний: {e}")

                # Поиск в социальных сетях
                if PARSER_CONFIG['use_social_media']:
                    try:
                        social_results = self._search_social_media(query, region)
                        suppliers.extend(social_results)
                        logger.info(f"Соцсети: найдено {len(social_results)} результатов")
                    except Exception as e:
                        logger.warning(f"Ошибка поиска в соцсетях: {e}")

                # Поиск на B2B-площадках
                b2b_results = self._search_b2b_sites(query, region)
                suppliers.extend(b2b_results)
                logger.info(f"B2B-площадки: найдено {len(b2b_results)} результатов")

            except Exception as e:
                logger.error(f"Ошибка при поиске по запросу '{query}': {e}")
                continue

            time.sleep(PARSER_CONFIG['delay_between_requests'])

        # Поиск через Perplexity AI (один раз для всех запросов)
        if self.perplexity_client:
            try:
                logger.info("🤖 Запуск поиска через Perplexity AI...")
                perplexity_results = self._search_perplexity_suppliers(product, region)
                suppliers.extend(perplexity_results)
                logger.info(f"Perplexity AI: найдено {len(perplexity_results)} результатов")
            except Exception as e:
                logger.error(f"Ошибка поиска через Perplexity AI: {e}")

        # Фильтруем и ранжируем результаты
        filtered_suppliers = self._filter_and_rank_suppliers(suppliers, product, region)

        logger.info(f"✅ Поиск завершен. Найдено {len(filtered_suppliers)} бизнес-поставщиков")
        return filtered_suppliers
    
    def _generate_business_queries(self, product: str, region: str) -> List[str]:
        """Улучшенная генерация бизнес-запросов для поиска производителей и дистрибьюторов"""
        queries: List[str] = []
        product_lower = product.lower()

        # Основные бизнес-запросы из конфигурации
        for category, keywords in BUSINESS_KEYWORDS.items():
            for keyword in keywords:
                # Стандартные запросы
                queries.append(f'"{product}" {keyword} {region}')
                queries.append(f'{product} {keyword} "{region}"')

                # Запросы с кавычками для точности
                queries.append(f'"{product}" "{keyword}" {region}')
                queries.append(f'"{product}" "{keyword}" "{region}"')

        # Специфические запросы для производителей
        producer_queries = [
            f'завод "{product}" {region}',
            f'производитель "{product}" {region}',
            f'фабрика "{product}" {region}',
            f'изготовитель "{product}" {region}',
            f'производство "{product}" {region}'
        ]
        queries.extend(producer_queries)

        # Специфические запросы для дистрибьюторов
        distributor_queries = [
            f'дистрибьютор "{product}" {region}',
            f'официальный дистрибьютор "{product}" {region}',
            f'эксклюзивный поставщик "{product}" {region}',
            f'представительство "{product}" {region}'
        ]
        queries.extend(distributor_queries)

        # Брендовые запросы
        brand_keywords = ["grohe", "hansgrohe", "villeroy", "duravit", "geberit", "bosch", "makita"]
        for brand in brand_keywords:
            if brand.lower() in product_lower:
                queries.extend([
                    f'"{brand}" дистрибьютор {region}',
                    f'"{brand}" официальный поставщик {region}',
                    f'"{brand}" дилер {region}',
                    f'"{brand}" партнер {region}'
                ])

        # Запросы для строительных материалов
        if any(word in product_lower for word in ['металл', 'арматура', 'труба', 'цемент', 'кирпич']):
            construction_queries = [
                f'"{product}" металлобаза {region}',
                f'"{product}" стройбаза {region}',
                f'"{product}" строительный рынок {region}',
                f'"{product}" оптовый склад {region}'
            ]
            queries.extend(construction_queries)

        # Удаляем дубликаты и ограничиваем количество
        unique_queries = list(set(queries))
        logger.info(f"Сгенерировано уникальных запросов: {len(unique_queries)}")

        return unique_queries[:20]  # Ограничиваем до 20 наиболее релевантных запросов
    
    def _search_google_suppliers(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Улучшенный поиск поставщиков в Google с более точными селекторами"""
        suppliers: List[Dict[str, Any]] = []

        try:
            if not self.driver:
                self.setup_driver()

            # Экранируем запрос для URL
            encoded_query = requests.utils.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}&num=20&hl=ru"

            logger.info(f"Открываем Google с запросом: {query}")
            self.driver.get(search_url)
            time.sleep(PARSER_CONFIG['delay_between_requests'] + 1)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Более точные селекторы для Google результатов
            search_results = []

            # Основные результаты поиска
            main_results = soup.find_all('div', class_='g')
            search_results.extend(main_results)

            # Результаты с сайтами компаний
            site_results = soup.find_all('div', {'data-ved': True})
            search_results.extend(site_results)

            # Удаляем дубликаты
            unique_results = []
            seen_urls = set()
            for result in search_results:
                url = result.find('a')
                if url and url.get('href'):
                    if url['href'] not in seen_urls:
                        seen_urls.add(url['href'])
                        unique_results.append(result)

            logger.info(f"Найдено уникальных результатов в Google: {len(unique_results)}")

            for i, result in enumerate(unique_results[:15]):
                try:
                    supplier = self._extract_google_supplier(result, query)
                    if supplier:
                        suppliers.append(supplier)
                        logger.debug(f"Извлечен поставщик {i+1}: {supplier.get('name', 'Unknown')}")

                except Exception as e:
                    logger.warning(f"Ошибка при парсинге Google результата {i+1}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка при поиске в Google: {e}")
            return []

        logger.info(f"Успешно извлечено {len(suppliers)} поставщиков из Google")
        return suppliers
    
    def _extract_google_supplier(self, result, query: str) -> Optional[Dict[str, Any]]:
        """Улучшенное извлечение данных поставщика из Google с расширенными селекторами"""
        try:
            # Ищем заголовок с различными селекторами
            title_elem = None

            # Попробуем разные селекторы для заголовка
            title_selectors = [
                'h3',
                'h3.LC20lb',
                'h3.zBAuLc',
                '.LC20lb',
                '.DKV0Md'
            ]

            for selector in title_selectors:
                title_elem = result.select_one(selector)
                if title_elem:
                    break

            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)

            # Проверяем минимальную длину названия
            if len(title) < 3:
                return None

            # Ищем ссылку с улучшенной обработкой
            link_elem = result.find('a')
            website = None

            if link_elem:
                href = link_elem.get('href', '')
                if href.startswith('/url?q='):
                    # Обрабатываем редирект Google
                    website = href.split('/url?q=')[1].split('&')[0]
                elif href.startswith('http'):
                    website = href
                elif not href.startswith('javascript:') and not href.startswith('#'):
                    website = href

            # Ищем описание с расширенными селекторами
            description = ""
            desc_selectors = [
                '.VwiC3b',
                '.aCOpRe',
                '.IsZvec',
                'span:not(.H9lube)',
                'div[data-ved] span'
            ]

            for selector in desc_selectors:
                desc_elem = result.select_one(selector)
                if desc_elem and len(desc_elem.get_text(strip=True)) > 10:
                    description = desc_elem.get_text(strip=True)
                    break

            # Извлекаем контакты из описания и заголовка
            full_text = f"{title} {description}"
            phone = self._extract_phone_from_text(full_text)
            email = self._extract_email_from_text(full_text)

            # Расширенная проверка бизнес-признаков
            business_score = self._calculate_business_score(title, description, query)
            is_business = business_score > 5

            # Определяем тип компании
            company_type = self._classify_company_from_text(title, description)

            # Создаем поставщика с расширенными данными
            supplier: Dict[str, Any] = {
                'name': title,
                'phone': phone,
                'email': email,
                'website': website,
                'description': description,
                'source': 'Google',
                'is_business': is_business,
                'company_type': company_type,
                'business_score': business_score,
                'relevance_score': self._calculate_business_relevance(title, query),
                'query': query,
                'extracted_at': datetime.now().isoformat()
            }

            # Добавляем бизнес-индикаторы
            supplier['business_indicators'] = self._extract_business_indicators(title, description)

            logger.debug(f"Извлечен поставщик: {title} (тип: {company_type}, счет: {business_score})")
            return supplier

        except Exception as e:
            logger.warning(f"Ошибка извлечения данных из Google: {e}")
            return None

    def _calculate_business_score(self, title: str, description: str, query: str) -> int:
        """Расчет комплексного бизнес-счета"""
        score = 0
        full_text = f"{title} {description}".lower()

        # Базовые бизнес-ключевые слова
        business_keywords = [
            'ооо', 'зао', 'ип', 'компания', 'фирма', 'группа', 'торг',
            'опт', 'оптовый', 'склад', 'база', 'поставщик', 'дистрибьютор',
            'производитель', 'завод', 'фабрика', 'изготовитель', 'выпускает'
        ]

        for keyword in business_keywords:
            if keyword in full_text:
                score += 2

        # Специфические слова для строительных материалов
        construction_keywords = [
            'строй', 'материал', 'цемент', 'бетон', 'кирпич', 'металл',
            'труба', 'арматура', 'инструмент', 'электро', 'сантехника'
        ]

        for keyword in construction_keywords:
            if keyword in full_text:
                score += 1

        # Наличие контактов
        if self._extract_phone_from_text(full_text):
            score += 3
        if self._extract_email_from_text(full_text):
            score += 2

        # Длина описания (длинные описания обычно более информативны)
        if len(description) > 50:
            score += 1

        return score

    def _classify_company_from_text(self, title: str, description: str) -> str:
        """Классификация типа компании по тексту"""
        full_text = f"{title} {description}".lower()

        # Производители
        if any(word in full_text for word in ['производитель', 'завод', 'фабрика', 'производство', 'изготовитель', 'выпускает']):
            return 'producer'

        # Дистрибьюторы
        elif any(word in full_text for word in ['дистрибьютор', 'официальный', 'представительство', 'партнер']):
            return 'distributor'

        # Оптовые поставщики
        elif any(word in full_text for word in ['опт', 'оптовый', 'склад', 'база', 'поставщик']):
            return 'wholesale'

        return 'unknown'

    def _extract_business_indicators(self, title: str, description: str) -> List[str]:
        """Извлечение бизнес-индикаторов из текста"""
        indicators = []
        full_text = f"{title} {description}".lower()

        business_terms = [
            'ооо', 'зао', 'ип', 'компания', 'фирма', 'группа', 'торг',
            'опт', 'оптовый', 'склад', 'база', 'поставщик', 'дистрибьютор',
            'производитель', 'завод', 'фабрика', 'изготовитель', 'выпускает',
            'официальный', 'представительство', 'партнер'
        ]

        for term in business_terms:
            if term in full_text:
                indicators.append(term)

        return indicators[:5]  # Ограничиваем до 5 индикаторов
    
    def _search_yandex_suppliers(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Улучшенный поиск поставщиков в Яндекс с расширенными селекторами"""
        suppliers: List[Dict[str, Any]] = []

        try:
            if not self.driver:
                self.setup_driver()

            encoded_query = requests.utils.quote(query)
            search_url = f"https://yandex.ru/search/?text={encoded_query}&lr=213&numdoc=20"

            logger.info(f"Открываем Яндекс с запросом: {query}")
            self.driver.get(search_url)
            time.sleep(PARSER_CONFIG['delay_between_requests'] + 1)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Расширенные селекторы для Яндекс результатов
            search_results = []

            # Основные результаты
            main_results = soup.find_all('div', class_=lambda x: x and 'serp-item' in x)
            search_results.extend(main_results)

            # Органические результаты
            organic_results = soup.find_all('li', class_=lambda x: x and 'serp-item' in x)
            search_results.extend(organic_results)

            # Удаляем дубликаты
            unique_results = []
            seen_urls = set()
            for result in search_results:
                url = result.find('a')
                if url and url.get('href'):
                    if url['href'] not in seen_urls:
                        seen_urls.add(url['href'])
                        unique_results.append(result)

            logger.info(f"Найдено уникальных результатов в Яндекс: {len(unique_results)}")

            for i, result in enumerate(unique_results[:12]):
                try:
                    supplier = self._extract_yandex_supplier(result, query)
                    if supplier:
                        suppliers.append(supplier)
                        logger.debug(f"Извлечен поставщик {i+1}: {supplier.get('name', 'Unknown')}")

                except Exception as e:
                    logger.warning(f"Ошибка при парсинге Яндекс результата {i+1}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка при поиске в Яндекс: {e}")
            return []

        logger.info(f"Успешно извлечено {len(suppliers)} поставщиков из Яндекс")
        return suppliers
    
    def _extract_yandex_supplier(self, result, query: str) -> Optional[Dict]:
        """Извлечение данных поставщика из Яндекс"""
        try:
            # Ищем заголовок
            title_elem = result.find('a', class_=lambda x: x and 'link' in x)
            if not title_elem:
                return None
                
            title = title_elem.get_text(strip=True)
            
            # Проверяем релевантность
            if not self._is_business_supplier(title, query):
                return None
            
            # Ищем ссылку
            website = title_elem.get('href') if title_elem else None
            
            # Ищем описание
            description_elem = result.find('div', class_=lambda x: x and 'text' in x)
            description = description_elem.get_text(strip=True) if description_elem else ""
            
            # Извлекаем контакты
            phone = self._extract_phone_from_text(description)
            email = self._extract_email_from_text(description)
            
            # Проверяем признаки бизнес-поставщика
            is_business = self._check_business_signs(title, description)
            
            supplier = {
                'name': title,
                'phone': phone,
                'email': email,
                'website': website,
                'description': description,
                'source': 'Yandex',
                'is_business': is_business,
                'relevance_score': self._calculate_business_relevance(title, query)
            }
            
            return supplier
            
        except Exception as e:
            print(f"Ошибка извлечения данных из Яндекс: {e}")
            return None
    
    def _search_business_catalogs(self, query: str, region: str) -> List[Dict]:
        """Расширенный поиск в бизнес-каталогах и справочниках"""
        suppliers = []

        # Расширенный список бизнес-каталогов с методами поиска
        business_catalogs = [
            ('Yandex Maps', "https://yandex.ru/maps", self._search_yandex_maps),
            ('RusList', "https://www.ruslist.ru", self._search_ruslist),
            ('YP Russia', "https://www.yp.ru", self._search_yp_catalog),
            ('2GIS', "https://www.2gis.ru", self._search_2gis_catalog),
            ('Yell.ru', "https://www.yell.ru", self._search_yell_catalog),
            ('Spravker', "https://www.spravker.ru", self._search_spravker),
            ('BizDir', "https://bizdir.ru", self._search_bizdir),
            ('FirmCard', "https://firmcard.ru", self._search_firmcard),
            ('OrgPage', "https://orgpage.ru", self._search_orgpage),
            ('AllBiz', "https://all.biz", self._search_allbiz),
            ('Rate.md', "https://rate.md", self._search_rate_md)
        ]

        # Добавляем поисковые системы если включены
        if PARSER_CONFIG['use_duckduckgo']:
            business_catalogs.append(('DuckDuckGo', "https://duckduckgo.com", self._search_duckduckgo))

        if PARSER_CONFIG['use_bing']:
            business_catalogs.append(('Bing', "https://www.bing.com", self._search_bing))

        for name, url, search_method in business_catalogs:
            try:
                logger.info(f"🔍 Поиск в {name}: {url}")
                catalog_results = search_method(query, region)
                suppliers.extend(catalog_results)
                logger.info(f"📊 {name}: найдено {len(catalog_results)} результатов")

                # Задержка между запросами
                time.sleep(PARSER_CONFIG['delay_between_requests'] * 0.5)

            except Exception as e:
                logger.warning(f"⚠️ Ошибка при поиске в {name}: {e}")

        return suppliers
    
    def _search_b2b_sites(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Расширенный поиск по B2B-площадкам и каталогам"""
        results: List[Dict[str, Any]] = []

        # Список B2B-площадок для поиска
        b2b_sites = [
            ('b2b_trade', self._search_b2b_trade),
            ('1c_market', self._search_1c_market),
            ('pulscen', self._search_pulscen),
            ('postavshhiki', self._search_postavshhiki),
            ('optlist', self._search_optlist),
            ('avito_business', self._search_avito_business),
            ('yell_catalog', self._search_yell_catalog),
            ('spravker', self._search_spravker),
            ('zoon_business', self._search_zoon_business),
            ('flamp_business', self._search_flamp_business)
        ]

        logger.info(f"Начинаем поиск по {len(b2b_sites)} B2B-площадкам")

        for site_name, search_func in b2b_sites:
            try:
                logger.debug(f"Поиск на {site_name}...")
                site_results = search_func(query, region)
                if site_results:
                    results.extend(site_results)
                    logger.info(f"{site_name}: найдено {len(site_results)} результатов")
                else:
                    logger.debug(f"{site_name}: результатов не найдено")

                # Небольшая задержка между запросами
                time.sleep(1)

            except Exception as e:
                logger.warning(f"Ошибка поиска на {site_name}: {e}")
                continue

        logger.info(f"Всего найдено на B2B-площадках: {len(results)}")
        return results

    def _search_b2b_trade(self, query: str, region: str) -> List[Dict]:
        """Поиск на b2b.trade"""
        results = []
        try:
            url = f"https://b2b.trade/search?query={requests.utils.quote(query + ' ' + region)}"
            resp = self.session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('a[href*="/suppliers/"]'):
                name = item.get_text(strip=True)
                link = item['href']
                if not link.startswith('http'):
                    link = 'https://b2b.trade' + link
                results.append({
                    'name': name,
                    'website': link,
                    'source': 'B2B.TRADE',
                    'is_business': True,
                    'relevance_score': 10,
                })
        except Exception as e:
            print(f"Ошибка парсинга b2b.trade: {e}")
        return results

    def _search_1c_market(self, query: str, region: str) -> List[Dict]:
        """Поиск на 1c.market"""
        results = []
        try:
            url = f"https://1c.market/search/?q={requests.utils.quote(query + ' ' + region)}"
            resp = self.session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('a[href*="/supplier/"]'):
                name = item.get_text(strip=True)
                link = item['href']
                if not link.startswith('http'):
                    link = 'https://1c.market' + link
                results.append({
                    'name': name,
                    'website': link,
                    'source': '1C.MARKET',
                    'is_business': True,
                    'relevance_score': 10,
                })
        except Exception as e:
            print(f"Ошибка парсинга 1c.market: {e}")
        return results

    def _search_pulscen(self, query: str, region: str) -> List[Dict]:
        """Поиск на pulscen.ru"""
        results = []
        try:
            url = f"https://www.pulscen.ru/search?query={requests.utils.quote(query + ' ' + region)}"
            resp = self.session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('a[href*="/company/"]'):
                name = item.get_text(strip=True)
                link = item['href']
                if not link.startswith('http'):
                    link = 'https://www.pulscen.ru' + link
                results.append({
                    'name': name,
                    'website': link,
                    'source': 'PULSCEN.RU',
                    'is_business': True,
                    'relevance_score': 10,
                })
        except Exception as e:
            print(f"Ошибка парсинга pulscen.ru: {e}")
        return results

    def _search_postavshhiki(self, query: str, region: str) -> List[Dict]:
        """Поиск на postavshhiki.ru"""
        results = []
        try:
            url = f"https://www.postavshhiki.ru/search/?q={requests.utils.quote(query + ' ' + region)}"
            resp = self.session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('a[href*="/company/"]'):
                name = item.get_text(strip=True)
                link = item['href']
                if not link.startswith('http'):
                    link = 'https://www.postavshhiki.ru' + link
                results.append({
                    'name': name,
                    'website': link,
                    'source': 'POSTAVSHHIKI.RU',
                    'is_business': True,
                    'relevance_score': 10,
                })
        except Exception as e:
            print(f"Ошибка парсинга postavshhiki.ru: {e}")
        return results

    def _search_optlist(self, query: str, region: str) -> List[Dict]:
        """Поиск на optlist.ru"""
        results = []
        try:
            url = f"https://optlist.ru/search/?q={requests.utils.quote(query + ' ' + region)}"
            resp = self.session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('a[href*="/company/"]'):
                name = item.get_text(strip=True)
                link = item['href']
                if not link.startswith('http'):
                    link = 'https://optlist.ru' + link
                results.append({
                    'name': name,
                    'website': link,
                    'source': 'OPTLIST.RU',
                    'is_business': True,
                    'relevance_score': 10,
                })
        except Exception as e:
            print(f"Ошибка парсинга optlist.ru: {e}")
        return results
    
    def _is_business_supplier(self, name: str, query: str) -> bool:
        """Проверка релевантности бизнес-поставщика"""
        name_lower = name.lower()
        query_lower = query.lower()
        
        # Ключевые слова для бизнес-поставщиков
        business_keywords = [
            'ооо', 'зао', 'ип', 'компания', 'фирма', 'группа', 'торг',
            'опт', 'оптовый', 'склад', 'база', 'поставщик', 'дистрибьютор',
            'производитель', 'официальный', 'представительство', 'торговый дом'
        ]
        
        # Проверяем наличие ключевых слов
        has_business_keywords = any(keyword in name_lower for keyword in business_keywords)
        
        # Проверяем соответствие запросу
        matches_query = any(word in name_lower for word in query_lower.split())
        
        return has_business_keywords or matches_query
    
    def _check_business_signs(self, name: str, text: str) -> bool:
        """Проверка признаков бизнес-поставщика"""
        text_lower = text.lower()
        
        business_indicators = [
            'опт', 'оптовый', 'склад', 'база', 'поставщик', 'дистрибьютор',
            'безналичный', 'перечисление', 'счет', 'договор', 'накладная',
            'отгрузка', 'доставка', 'грузоперевозки', 'производитель',
            'официальный поставщик', 'торговый дом', 'компания'
        ]
        
        return any(indicator in text_lower for indicator in business_indicators)
    
    def _calculate_business_relevance(self, name: str, query: str) -> int:
        """Расчет релевантности для бизнеса"""
        score = 0
        name_lower = name.lower()
        query_lower = query.lower()
        
        # Бонус за точное совпадение
        if query_lower in name_lower:
            score += 15
        
        # Бонус за ключевые слова бизнеса
        business_keywords = ['опт', 'склад', 'база', 'поставщик', 'дистрибьютор', 'производитель']
        for keyword in business_keywords:
            if keyword in name_lower:
                score += 8
        
        # Бонус за наличие контактов
        if self._extract_phone_from_text(name):
            score += 5
        
        # Бонус за официальность
        official_keywords = ['официальный', 'дистрибьютор', 'производитель']
        for keyword in official_keywords:
            if keyword in name_lower:
                score += 10
        
        return score
    
    def _filter_and_rank_suppliers(self, suppliers: List[Dict[str, Any]], product: str, region: str) -> List[Dict[str, Any]]:
        """Улучшенная фильтрация и ранжирование поставщиков с фокусом на производителей и дистрибьюторов"""
        if not suppliers:
            logger.warning("Нет поставщиков для фильтрации")
            return []

        # Удаляем дубликаты
        unique_suppliers: List[Dict[str, Any]] = []
        seen_names: set[str] = set()

        for supplier in suppliers:
            normalized_name = supplier['name'].lower().strip()
            if normalized_name not in seen_names and len(normalized_name) > 2:
                seen_names.add(normalized_name)
                unique_suppliers.append(supplier)

        logger.info(f"Удалено дубликатов: {len(suppliers) - len(unique_suppliers)}")

        # Расширенная фильтрация и классификация компаний
        filtered_suppliers = []
        for supplier in unique_suppliers:
            supplier = self._classify_company_type(supplier, product)
            supplier = self._calculate_enhanced_relevance(supplier, product, region)
            filtered_suppliers.append(supplier)

        # Сортируем по комплексному рейтингу
        filtered_suppliers.sort(key=lambda x: (
            x.get('company_priority', 0),  # Приоритет типа компании
            x.get('relevance_score', 0),   # Релевантность
            x.get('contact_score', 0)      # Качество контактов
        ), reverse=True)

        # Фильтруем только наиболее релевантных поставщиков
        top_suppliers = [s for s in filtered_suppliers if s.get('company_priority', 0) > 0][:50]

        logger.info("📊 Статистика фильтрации:")
        logger.info(f"Всего найдено: {len(suppliers)}")
        logger.info(f"Уникальных: {len(unique_suppliers)}")
        logger.info(f"После фильтрации: {len(top_suppliers)}")

        # Логируем типы найденных компаний
        company_types = {}
        for supplier in top_suppliers:
            company_type = supplier.get('company_type', 'unknown')
            company_types[company_type] = company_types.get(company_type, 0) + 1

        logger.info(f"Распределение по типам компаний: {company_types}")

        return top_suppliers

    def _classify_company_type(self, supplier: Dict[str, Any], product: str) -> Dict[str, Any]:
        """Классификация типа компании и определение приоритета"""
        name = supplier.get('name', '').lower()
        description = supplier.get('description', '').lower()

        # Определяем тип компании
        company_type = 'unknown'
        priority = 0

        # Производители (высокий приоритет)
        producer_keywords = BUSINESS_KEYWORDS['producer'] + ['завод', 'фабрика', 'производство']
        if any(keyword in name or keyword in description for keyword in producer_keywords):
            company_type = 'producer'
            priority = 10

        # Дистрибьюторы (высокий приоритет)
        elif any(keyword in name or keyword in description for keyword in BUSINESS_KEYWORDS['distributor']):
            company_type = 'distributor'
            priority = 9

        # Оптовые поставщики
        elif any(keyword in name or keyword in description for keyword in BUSINESS_KEYWORDS['wholesale']):
            company_type = 'wholesale'
            priority = 7

        # Склады и базы
        elif any(keyword in name or keyword in description for keyword in BUSINESS_KEYWORDS['warehouse']):
            company_type = 'warehouse'
            priority = 6

        # Общие поставщики
        elif any(keyword in name or keyword in description for keyword in BUSINESS_KEYWORDS['supplier']):
            company_type = 'supplier'
            priority = 5

        supplier['company_type'] = company_type
        supplier['company_priority'] = priority

        return supplier

    def _calculate_enhanced_relevance(self, supplier: Dict[str, Any], product: str, region: str) -> Dict[str, Any]:
        """Расширенный расчет релевантности"""
        score = supplier.get('relevance_score', 0)
        name = supplier.get('name', '').lower()

        # Бонус за точное совпадение продукта
        if product.lower() in name:
            score += 20

        # Бонус за наличие бизнес-ключевых слов
        business_indicators = []
        for category, keywords in BUSINESS_KEYWORDS.items():
            for keyword in keywords:
                if keyword in name:
                    score += 5
                    business_indicators.append(keyword)

        # Бонус за контакты
        contact_score = 0
        if supplier.get('phone'):
            contact_score += 10
        if supplier.get('email'):
            contact_score += 10
        if supplier.get('website'):
            contact_score += 15

        # Бонус за регион
        if region.lower() in str(supplier.get('description', '')):
            score += 5

        # Штраф за слишком короткие названия
        if len(supplier.get('name', '')) < 5:
            score -= 10

        supplier['relevance_score'] = max(0, score)
        supplier['contact_score'] = contact_score
        supplier['business_indicators'] = business_indicators

        return supplier
    
    def _extract_phone_from_text(self, text: str) -> Optional[str]:
        """Извлечение телефона из текста"""
        phone_pattern = r'(\+7|8)[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{3})[\s\-\(\)]*(\d{2})[\s\-\(\)]*(\d{2})'
        
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            return phone_match.group(0)
        return None
    
    def _extract_email_from_text(self, text: str) -> Optional[str]:
        """Извлечение email из текста"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        email_match = re.search(email_pattern, text)
        if email_match:
            return email_match.group(0)
        return None
    
    def __del__(self):
        """Деструктор"""
        self.close_driver()

def test_business_supplier_finder():
    """Тест поисковика бизнес-поставщиков"""
    print("🧪 Тест поисковика бизнес-поставщиков")
    print("=" * 60)
    
    finder = BusinessSupplierFinder()
    
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
            print(f"\n✅ Найдено бизнес-поставщиков: {len(suppliers)}")
            for j, supplier in enumerate(suppliers[:5], 1):
                print(f"\n{j}. {supplier['name']}")
                print(f"   📞 Телефон: {supplier.get('phone', 'Не указан')}")
                print(f"   📧 Email: {supplier.get('email', 'Не указан')}")
                print(f"   🌐 Сайт: {supplier.get('website', 'Не указан')}")
                print(f"   📊 Релевантность: {supplier.get('relevance_score', 0)}")
                print(f"   🏢 Бизнес-поставщик: {'Да' if supplier.get('is_business') else 'Нет'}")
                print(f"   📋 Источник: {supplier.get('source', 'Неизвестно')}")
        else:
            print("❌ Бизнес-поставщики не найдены")
    
    finder.close_driver()

    # Новые источники поиска

    def _search_avito_business(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск бизнес-поставщиков на Avito"""
        results: List[Dict[str, Any]] = []
        try:
            search_url = f"https://www.avito.ru/{region.lower()}/predlazheniya_uslug?q={requests.utils.quote(query)}&s=104"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('[data-marker="item"]')[:8]:
                try:
                    title_elem = item.select_one('[itemprop="name"], .title, h3')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)

                    # Проверяем, что это бизнес-предложение
                    if not any(word in title.lower() for word in ['опт', 'поставка', 'компания', 'ооо', 'зао']):
                        continue

                    link_elem = item.select_one('a[href]')
                    website = link_elem['href'] if link_elem else None

                    results.append({
                        'name': title,
                        'website': f"https://www.avito.ru{website}" if website else None,
                        'source': 'Avito Business',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 8
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга Avito: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Ошибка поиска на Avito: {e}")

        return results

    def _search_yell_catalog(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в каталоге Yell.ru"""
        results: List[Dict[str, Any]] = []
        try:
            search_url = f"https://www.yell.ru/search/{region.lower()}/?q={requests.utils.quote(query)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.business-card, .company-item')[:6]:
                try:
                    title_elem = item.select_one('h3, .title, .name')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link_elem = item.select_one('a')
                    website = link_elem.get('href') if link_elem else None

                    results.append({
                        'name': title,
                        'website': website,
                        'source': 'Yell.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 7
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга Yell.ru: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Ошибка поиска на Yell.ru: {e}")

        return results

    def _search_spravker(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в справочнике Spravker.ru"""
        results: List[Dict[str, Any]] = []
        try:
            search_url = f"https://www.spravker.ru/search/?q={requests.utils.quote(query + ' ' + region)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.company-item, .business-item')[:6]:
                try:
                    title_elem = item.select_one('.company-name, .title, h4')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    phone_elem = item.select_one('.phone, .contact-phone')
                    phone = phone_elem.get_text(strip=True) if phone_elem else None

                    results.append({
                        'name': title,
                        'phone': phone,
                        'source': 'Spravker.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 7
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга Spravker.ru: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Ошибка поиска на Spravker.ru: {e}")

        return results

    def _search_zoon_business(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в каталоге Zoon.ru"""
        results: List[Dict[str, Any]] = []
        try:
            search_url = f"https://zoon.ru/search/?query={requests.utils.quote(query + ' ' + region)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('[data-zoon-type="business"]')[:6]:
                try:
                    title_elem = item.select_one('.title, h4, .name')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    rating_elem = item.select_one('.rating, .stars')
                    rating = rating_elem.get_text(strip=True) if rating_elem else None

                    results.append({
                        'name': title,
                        'source': 'Zoon.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 8 if rating else 6,
                        'notes': f"Рейтинг: {rating}" if rating else None
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга Zoon.ru: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Ошибка поиска на Zoon.ru: {e}")

        return results

    def _search_flamp_business(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в каталоге Flamp.ru"""
        results: List[Dict[str, Any]] = []
        try:
            search_url = f"https://flamp.ru/search/{region.lower()}/?query={requests.utils.quote(query)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.company-item, .business-card')[:6]:
                try:
                    title_elem = item.select_one('.company-name, .title, h3')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    address_elem = item.select_one('.address, .location')
                    address = address_elem.get_text(strip=True) if address_elem else None

                    results.append({
                        'name': title,
                        'address': address,
                        'source': 'Flamp.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 7
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга Flamp.ru: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Ошибка поиска на Flamp.ru: {e}")

        return results

    def _search_perplexity_suppliers(self, product: str, region: str) -> List[Dict[str, Any]]:
        """
        Поиск поставщиков через Perplexity AI API
        Использует AI для интеллектуального поиска бизнес-поставщиков
        """
        results: List[Dict[str, Any]] = []

        if not self.perplexity_client:
            logger.info("⏭️ Perplexity API недоступен, пропускаем поиск")
            return results

        try:
            logger.info(f"🤖 Начинаем поиск через Perplexity AI: {product} в {region}")

            # Формируем умный запрос для Perplexity
            prompt = f"""
            Найди производителей, дистрибьюторов и крупных поставщиков товара "{product}" в регионе "{region}".

            Для каждого найденного поставщика предоставь следующую информацию в формате JSON:
            - name: название компании
            - phone: телефон (если найден)
            - email: email (если найден)
            - website: сайт (если найден)
            - address: адрес
            - company_type: тип компании (producer/distributor/wholesale_supplier/supplier)
            - description: краткое описание деятельности

            Найди минимум {PERPLEXITY_CONFIG['max_results']} компаний.
            Отдавай предпочтение проверенным компаниям с хорошей репутацией.
            Исключи мелких розничных продавцов.

            Верни результат в формате JSON массива объектов.
            """

            # Отправляем запрос к Perplexity API
            response = self.perplexity_client.chat.completions.create(
                model=PERPLEXITY_CONFIG['model'],
                messages=[
                    {"role": "system", "content": "Ты - эксперт по поиску бизнес-поставщиков в России. Возвращай только JSON без дополнительного текста."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=PERPLEXITY_CONFIG['max_tokens'],
                temperature=PERPLEXITY_CONFIG['temperature'],
                timeout=PERPLEXITY_CONFIG['search_timeout']
            )

            # Парсим ответ от Perplexity
            content = response.choices[0].message.content.strip()
            logger.debug(f"Ответ от Perplexity: {content[:500]}...")

            # Пытаемся извлечь JSON из ответа
            try:
                # Ищем JSON массив в ответе
                json_start = content.find('[')
                json_end = content.rfind(']') + 1

                if json_start != -1 and json_end > json_start:
                    json_content = content[json_start:json_end]
                    suppliers_data = json.loads(json_content)

                    for supplier_data in suppliers_data[:PERPLEXITY_CONFIG['max_results']]:
                        try:
                            # Создаем объект поставщика
                            supplier = {
                                'name': supplier_data.get('name', 'Неизвестная компания'),
                                'phone': supplier_data.get('phone'),
                                'email': supplier_data.get('email'),
                                'website': supplier_data.get('website'),
                                'address': supplier_data.get('address'),
                                'source': 'Perplexity AI',
                                'is_business': True,
                                'company_type': supplier_data.get('company_type', 'supplier'),
                                'relevance_score': 9,  # Высокий рейтинг от AI
                                'description': supplier_data.get('description', ''),
                                'ai_generated': True  # Маркер AI-генерированных данных
                            }

                            # Валидация данных
                            if len(supplier['name']) > 3:  # Минимум 3 символа в названии
                                results.append(supplier)
                                logger.debug(f"Извлечен AI-поставщик: {supplier['name']}")

                        except Exception as e:
                            logger.warning(f"Ошибка обработки AI-данных: {e}")
                            continue

                    logger.info(f"✅ Perplexity нашел {len(results)} поставщиков")

                else:
                    logger.warning("Не удалось найти JSON в ответе Perplexity")
                    # Попытка извлечь информацию из текстового ответа
                    self._extract_suppliers_from_text(content, results)

            except json.JSONDecodeError as e:
                logger.warning(f"Ошибка парсинга JSON от Perplexity: {e}")
                # Попытка извлечь информацию из текстового ответа
                self._extract_suppliers_from_text(content, results)

        except Exception as e:
            logger.error(f"❌ Ошибка поиска через Perplexity API: {e}")

        return results

    def _extract_suppliers_from_text(self, text: str, results: List[Dict[str, Any]]) -> None:
        """
        Извлечение информации о поставщиках из текстового ответа Perplexity
        Fallback метод для обработки неструктурированного текста
        """
        try:
            lines = text.split('\n')
            current_supplier = {}

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Ищем название компании
                if any(keyword in line.lower() for keyword in ['компания', 'завод', 'производитель', 'дистрибьютор']):
                    if current_supplier and current_supplier.get('name'):
                        results.append(current_supplier)
                    current_supplier = {'name': line, 'source': 'Perplexity AI (text)', 'is_business': True}

                # Ищем контактную информацию
                elif current_supplier:
                    if 'тел:' in line.lower() or 'телефон:' in line.lower():
                        phone_match = re.search(r'[\+]?[7-8][\d\s\-\(\)]{10,}', line)
                        if phone_match:
                            current_supplier['phone'] = phone_match.group(0).strip()

                    elif '@' in line and '.' in line:
                        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
                        if email_match:
                            current_supplier['email'] = email_match.group(0).strip()

                    elif 'http' in line or 'www' in line:
                        url_match = re.search(r'https?://[^\s]+', line)
                        if url_match:
                            current_supplier['website'] = url_match.group(0).strip()

            # Добавляем последнего поставщика
            if current_supplier and current_supplier.get('name'):
                results.append(current_supplier)

            logger.info(f"Извлечено {len(results)} поставщиков из текстового ответа")

        except Exception as e:
            logger.error(f"Ошибка извлечения из текста: {e}")

    # Новые методы поиска в каталогах

    def _search_ruslist(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в RusList.ru"""
        results = []
        try:
            search_url = f"https://www.ruslist.ru/search?q={requests.utils.quote(query)}+{requests.utils.quote(region)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.company-item, .business-card, .firm-item')[:8]:
                try:
                    name_elem = item.select_one('.company-name, .title, h3, h4, .name')
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if len(name) < 3:
                        continue

                    results.append({
                        'name': name,
                        'source': 'RusList.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 6
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга RusList: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска на RusList: {e}")

        return results

    def _search_yp_catalog(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в YP Russia"""
        results = []
        try:
            search_url = f"https://www.yp.ru/search/?query={requests.utils.quote(query)}+{requests.utils.quote(region)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.business-card, .company-item, .result-item')[:8]:
                try:
                    name_elem = item.select_one('.business-name, .company-name, .title, h3')
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if len(name) < 3:
                        continue

                    # Извлекаем адрес если есть
                    address_elem = item.select_one('.address, .location')
                    address = address_elem.get_text(strip=True) if address_elem else None

                    results.append({
                        'name': name,
                        'address': address,
                        'source': 'YP.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 6
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга YP: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска на YP: {e}")

        return results

    def _search_2gis_catalog(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в 2GIS"""
        results = []
        try:
            # Для 2GIS используем поисковый запрос
            search_url = f"https://2gis.ru/{region.lower()}/search/{requests.utils.quote(query)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.searchResults__item, ._1h3cgic, [data-testid="search-result"]')[:8]:
                try:
                    name_elem = item.select_one('._1h3cgic, .searchResult__title, [data-testid="search-result-title"]')
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if len(name) < 3:
                        continue

                    # Извлекаем адрес
                    address_elem = item.select_one('._z72pvu, .searchResult__address')
                    address = address_elem.get_text(strip=True) if address_elem else None

                    results.append({
                        'name': name,
                        'address': address,
                        'source': '2GIS',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 7
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга 2GIS: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска на 2GIS: {e}")

        return results

    def _search_bizdir(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в BizDir.ru"""
        results = []
        try:
            search_url = f"https://bizdir.ru/search/{requests.utils.quote(region)}/{requests.utils.quote(query)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.company-item, .business-card, .result')[:8]:
                try:
                    name_elem = item.select_one('.company-name, .name, h3, h4')
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if len(name) < 3:
                        continue

                    # Извлекаем дополнительные данные
                    phone_elem = item.select_one('.phone, .tel')
                    phone = phone_elem.get_text(strip=True) if phone_elem else None

                    results.append({
                        'name': name,
                        'phone': phone,
                        'source': 'BizDir.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 6
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга BizDir: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска на BizDir: {e}")

        return results

    def _search_firmcard(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в FirmCard.ru"""
        results = []
        try:
            search_url = f"https://firmcard.ru/search/?q={requests.utils.quote(query)}+{requests.utils.quote(region)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.firm-item, .company-item, .result')[:8]:
                try:
                    name_elem = item.select_one('.firm-name, .company-name, .title, h3')
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if len(name) < 3:
                        continue

                    # Извлекаем контакты
                    contact_elem = item.select_one('.contacts, .contact-info')
                    contact_text = contact_elem.get_text(strip=True) if contact_elem else ""

                    # Ищем телефон
                    phone_match = re.search(r'[\+]?[78][\d\s\-\(\)]{10,}', contact_text)
                    phone = phone_match.group(0).strip() if phone_match else None

                    results.append({
                        'name': name,
                        'phone': phone,
                        'source': 'FirmCard.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 6
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга FirmCard: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска на FirmCard: {e}")

        return results

    def _search_orgpage(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в OrgPage.ru"""
        results = []
        try:
            search_url = f"https://orgpage.ru/{region.lower()}/search/{requests.utils.quote(query)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.org-item, .company-item, .result')[:8]:
                try:
                    name_elem = item.select_one('.org-name, .company-name, .title, h3')
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if len(name) < 3:
                        continue

                    # Извлекаем описание
                    desc_elem = item.select_one('.description, .info')
                    description = desc_elem.get_text(strip=True) if desc_elem else None

                    results.append({
                        'name': name,
                        'description': description,
                        'source': 'OrgPage.ru',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 5
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга OrgPage: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска на OrgPage: {e}")

        return results

    def _search_allbiz(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в AllBiz.net"""
        results = []
        try:
            search_url = f"https://all.biz/search?q={requests.utils.quote(query)}+{requests.utils.quote(region)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.company-item, .supplier-item, .result')[:8]:
                try:
                    name_elem = item.select_one('.company-name, .supplier-name, .title, h3')
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if len(name) < 3:
                        continue

                    # Извлекаем категорию
                    category_elem = item.select_one('.category, .type')
                    category = category_elem.get_text(strip=True) if category_elem else None

                    results.append({
                        'name': name,
                        'description': category,
                        'source': 'AllBiz.net',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 7
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга AllBiz: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска на AllBiz: {e}")

        return results

    def _search_rate_md(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в Rate.md"""
        results = []
        try:
            search_url = f"https://rate.md/search/{requests.utils.quote(region)}/{requests.utils.quote(query)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.company-item, .business-item, .result')[:8]:
                try:
                    name_elem = item.select_one('.company-name, .business-name, .title, h3')
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if len(name) < 3:
                        continue

                    # Извлекаем рейтинг
                    rating_elem = item.select_one('.rating, .stars')
                    rating = rating_elem.get_text(strip=True) if rating_elem else None

                    results.append({
                        'name': name,
                        'description': f"Рейтинг: {rating}" if rating else None,
                        'source': 'Rate.md',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 5
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга Rate.md: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска на Rate.md: {e}")

        return results

    def _search_yandex_maps(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в Яндекс.Картах"""
        results = []
        try:
            # Используем API Яндекс.Карт для поиска организаций
            search_url = f"https://yandex.ru/maps/213/moscow/search/{requests.utils.quote(query)}"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])

            # Ищем JSON данные в HTML
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Ищем скрипт с данными
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'organizations' in script.string:
                    try:
                        # Пытаемся извлечь данные из JavaScript
                        script_text = script.string

                        # Ищем названия организаций
                        org_matches = re.findall(r'"name"\s*:\s*"([^"]+)"', script_text)
                        address_matches = re.findall(r'"address"\s*:\s*"([^"]+)"', script_text)

                        for i, org_name in enumerate(org_matches[:8]):
                            if len(org_name) > 3:
                                address = address_matches[i] if i < len(address_matches) else None

                                results.append({
                                    'name': org_name,
                                    'address': address,
                                    'source': 'Yandex Maps',
                                    'is_business': True,
                                    'company_type': 'supplier',
                                    'relevance_score': 8
                                })

                    except Exception as e:
                        logger.warning(f"Ошибка парсинга JavaScript в Yandex Maps: {e}")

            # Если не нашли в скриптах, пробуем обычный парсинг
            if not results:
                for item in soup.select('.search-business-snippet, .org-snippet, .business-card')[:8]:
                    try:
                        name_elem = item.select_one('.business-name, .org-name, .title, h3')
                        if not name_elem:
                            continue

                        name = name_elem.get_text(strip=True)
                        if len(name) < 3:
                            continue

                        address_elem = item.select_one('.business-address, .org-address, .address')
                        address = address_elem.get_text(strip=True) if address_elem else None

                        results.append({
                            'name': name,
                            'address': address,
                            'source': 'Yandex Maps',
                            'is_business': True,
                            'company_type': 'supplier',
                            'relevance_score': 8
                        })

                    except Exception as e:
                        logger.warning(f"Ошибка парсинга Yandex Maps: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска в Yandex Maps: {e}")

        return results

    def _search_duckduckgo(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск через DuckDuckGo"""
        results = []
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}+{requests.utils.quote(region)}+поставщик+производитель"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.result, .results_links_deep')[:10]:
                try:
                    title_elem = item.select_one('.result__title, h2')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    if len(title) < 3:
                        continue

                    # Извлекаем URL
                    url_elem = item.select_one('.result__url, .result__extras__url')
                    url = url_elem.get_text(strip=True) if url_elem else None

                    # Извлекаем описание
                    desc_elem = item.select_one('.result__snippet, .result__extras')
                    description = desc_elem.get_text(strip=True) if desc_elem else None

                    results.append({
                        'name': title,
                        'website': url,
                        'description': description,
                        'source': 'DuckDuckGo',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 5
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга DuckDuckGo: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска в DuckDuckGo: {e}")

        return results

    def _search_bing(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск через Bing"""
        results = []
        try:
            search_url = f"https://www.bing.com/search?q={requests.utils.quote(query)}+{requests.utils.quote(region)}+поставщик+производитель"
            resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('.b_algo, .b_ans, h2')[:10]:
                try:
                    title_elem = item.select_one('h2, .b_algo h2')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    if len(title) < 3:
                        continue

                    # Извлекаем URL
                    url_elem = item.select_one('cite, .b_attribution cite')
                    url = url_elem.get_text(strip=True) if url_elem else None

                    # Извлекаем описание
                    desc_elem = item.select_one('.b_caption p, .b_snippet')
                    description = desc_elem.get_text(strip=True) if desc_elem else None

                    results.append({
                        'name': title,
                        'website': url,
                        'description': description,
                        'source': 'Bing',
                        'is_business': True,
                        'company_type': 'supplier',
                        'relevance_score': 5
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга Bing: {e}")

        except Exception as e:
            logger.warning(f"Ошибка поиска в Bing: {e}")

        return results

    def _search_company_websites(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск на сайтах компаний напрямую"""
        results = []
        company_domains = [
            'metalloprokat.ru', 'stroymaterialy.ru', 'santehnika.ru',
            'instrumenty.ru', 'elektrooborudovanie.ru', 'otdelka.ru',
            'biznes.ru', 'company.ru', 'firm.ru', 'org.ru'
        ]

        for domain in company_domains[:3]:  # Ограничиваем для производительности
            try:
                search_url = f"https://www.{domain}/search?q={requests.utils.quote(query)}"
                resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    # Ищем информацию о компании на главной странице
                    title_elem = soup.select_one('title')
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        if query.lower() in title.lower() and len(title) > 3:
                            results.append({
                                'name': title,
                                'website': f"https://www.{domain}",
                                'source': f'Company Website ({domain})',
                                'is_business': True,
                                'company_type': 'supplier',
                                'relevance_score': 8
                            })

                time.sleep(0.5)  # Задержка между запросами

            except Exception as e:
                logger.debug(f"Ошибка поиска на {domain}: {e}")

        return results

    def _search_social_media(self, query: str, region: str) -> List[Dict[str, Any]]:
        """Поиск в социальных сетях и профессиональных сообществах"""
        results = []
        social_sources = [
            ('VK Business', f"https://vk.com/search?c[q]={requests.utils.quote(query)}+{requests.utils.quote(region)}&c[type]=communities"),
            ('Telegram Channels', f"https://t.me/s/{requests.utils.quote(query)}_{requests.utils.quote(region)}")
        ]

        for name, search_url in social_sources:
            try:
                resp = self.session.get(search_url, timeout=PARSER_CONFIG['timeout'])

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    # Для VK
                    if 'vk.com' in search_url:
                        for item in soup.select('.groups_row, .group_row')[:3]:
                            name_elem = item.select_one('.group_name, .group_title')
                            if name_elem:
                                group_name = name_elem.get_text(strip=True)
                                if len(group_name) > 3:
                                    results.append({
                                        'name': group_name,
                                        'source': 'VK Business',
                                        'is_business': True,
                                        'company_type': 'supplier',
                                        'relevance_score': 4
                                    })

                    # Для Telegram
                    elif 't.me' in search_url:
                        for item in soup.select('.tgme_channel_info, .channel-info')[:3]:
                            name_elem = item.select_one('.tgme_channel_title, .channel-title')
                            if name_elem:
                                channel_name = name_elem.get_text(strip=True)
                                if len(channel_name) > 3:
                                    results.append({
                                        'name': channel_name,
                                        'source': 'Telegram',
                                        'is_business': True,
                                        'company_type': 'supplier',
                                        'relevance_score': 4
                                    })

                time.sleep(1)  # Задержка между запросами к соцсетям

            except Exception as e:
                logger.debug(f"Ошибка поиска в {name}: {e}")

        return results

if __name__ == "__main__":
    test_business_supplier_finder() 