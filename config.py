import os
import logging
from dotenv import load_dotenv
from typing import Dict, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('supplier_search.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

load_dotenv()

# Настройки парсера
PARSER_CONFIG = {
    'delay_between_requests': int(os.getenv('DELAY_BETWEEN_REQUESTS', 2)),
    'max_retries': int(os.getenv('MAX_RETRIES', 3)),
    'timeout': int(os.getenv('REQUEST_TIMEOUT', 30)),
    'user_agent': os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
    'max_concurrent_requests': int(os.getenv('MAX_CONCURRENT_REQUESTS', 3)),
    'search_timeout': int(os.getenv('SEARCH_TIMEOUT', 60)),
    'use_business_catalogs': os.getenv('USE_BUSINESS_CATALOGS', 'true').lower() == 'true',
    'use_company_websites': os.getenv('USE_COMPANY_WEBSITES', 'true').lower() == 'true',
    'use_social_media': os.getenv('USE_SOCIAL_MEDIA', 'true').lower() == 'true',
    'use_duckduckgo': os.getenv('USE_DUCKDUCKGO', 'true').lower() == 'true',
    'use_bing': os.getenv('USE_BING', 'true').lower() == 'true'
}

# Настройки Perplexity API
PERPLEXITY_CONFIG = {
    'api_key': os.getenv('PERPLEXITY_API_KEY'),
    'base_url': 'https://api.perplexity.ai',
    'model': os.getenv('PERPLEXITY_MODEL', 'sonar-pro'),
    'max_tokens': int(os.getenv('PERPLEXITY_MAX_TOKENS', 2048)),
    'temperature': float(os.getenv('PERPLEXITY_TEMPERATURE', 0.1)),
    'enabled': os.getenv('PERPLEXITY_ENABLED', 'false').lower() == 'true',
    'search_timeout': int(os.getenv('PERPLEXITY_SEARCH_TIMEOUT', 30)),
    'max_results': int(os.getenv('PERPLEXITY_MAX_RESULTS', 10))
}

# Улучшенные ключевые слова для поиска производителей и дистрибьюторов
BUSINESS_KEYWORDS = {
    'producer': ['производитель', 'завод', 'фабрика', 'производство', 'изготовитель', 'выпускает'],
    'distributor': ['дистрибьютор', 'официальный дистрибьютор', 'эксклюзивный дистрибьютор', 'представительство'],
    'wholesale': ['опт', 'оптовый', 'оптовая продажа', 'оптовый поставщик', 'крупный опт'],
    'supplier': ['поставщик', 'поставка', 'поставляет', 'поставки', 'компания-поставщик'],
    'warehouse': ['склад', 'база', 'складской комплекс', 'логистический центр', 'хранение'],
    'company_types': ['ООО', 'ЗАО', 'ПАО', 'АО', 'ИП', 'Группа компаний', 'Холдинг']
}

# Категории строительных материалов с улучшенными ключевыми словами
CATEGORIES: Dict[str, Dict] = {
    'metalloprokat': {
        'name': 'Металлопрокат',
        'keywords': ['металлопрокат', 'арматура', 'труба', 'лист', 'уголок', 'швеллер', 'двутавр', 'балка', 'штрипс'],
        'subcategories': ['арматура', 'трубы', 'листы', 'уголки', 'швеллеры', 'двутавры', 'профили'],
        'producer_keywords': ['металлургический завод', 'металлургический комбинат', 'сталелитейный завод'],
        'supplier_keywords': ['металлобаза', 'металлотрейдер', 'металлоснабжение']
    },
    'santehnika': {
        'name': 'Сантехника',
        'keywords': ['сантехника', 'трубы', 'краны', 'смесители', 'унитазы', 'раковины', 'ванны', 'душевая кабина'],
        'subcategories': ['трубы', 'краны', 'смесители', 'санфаянс', 'ванны', 'душевые кабины'],
        'producer_keywords': ['завод сантехники', 'производитель сантехники', 'фабрика санфаянс'],
        'supplier_keywords': ['дистрибьютор сантехники', 'поставщик сантехники', 'сантехническая компания']
    },
    'stroymaterialy': {
        'name': 'Строительные материалы',
        'keywords': ['цемент', 'бетон', 'кирпич', 'блоки', 'песок', 'щебень', 'гипс', 'сухие смеси'],
        'subcategories': ['цемент', 'бетон', 'кирпич', 'блоки', 'песок', 'щебень', 'гипс'],
        'producer_keywords': ['цементный завод', 'кирпичный завод', 'бетонный завод', 'производитель бетона'],
        'supplier_keywords': ['стройбаза', 'стройматериалы', 'строительный рынок', 'комплекс поставок']
    },
    'instrumenty': {
        'name': 'Инструменты',
        'keywords': ['инструменты', 'электроинструмент', 'перфоратор', 'дрель', 'болгарка', 'шлифмашина'],
        'subcategories': ['электроинструмент', 'ручной инструмент', 'измерительные приборы'],
        'producer_keywords': ['завод инструментов', 'производитель инструментов', 'фабрика инструментов'],
        'supplier_keywords': ['дистрибьютор инструментов', 'поставщик инструментов', 'инструментальная компания']
    },
    'elektrooborudovanie': {
        'name': 'Электрооборудование',
        'keywords': ['электрооборудование', 'кабель', 'провод', 'светильники', 'розетки', 'выключатели', 'щит'],
        'subcategories': ['кабель', 'провод', 'светильники', 'электрофурнитура', 'щиты'],
        'producer_keywords': ['завод электротехники', 'кабельный завод', 'производитель кабеля'],
        'supplier_keywords': ['электротехническая компания', 'электроснабжение', 'энергоснабжение']
    },
    'otdelochnye_materialy': {
        'name': 'Отделочные материалы',
        'keywords': ['обои', 'краска', 'штукатурка', 'плитка', 'ламинат', 'паркет', 'линолеум', 'гипсокартон'],
        'subcategories': ['обои', 'краска', 'штукатурка', 'плитка', 'напольные покрытия'],
        'producer_keywords': ['завод отделочных материалов', 'производитель красок', 'фабрика обоев'],
        'supplier_keywords': ['дистрибьютор отделки', 'поставщик отделочных материалов', 'компания отделочных материалов']
    }
}

# Источники для парсинга
SOURCES = [
    'https://www.avito.ru',
    'https://www.yandex.ru/maps',
    'https://2gis.ru',
    'https://www.ruslist.ru',
    'https://www.yp.ru'
]

# Настройки Excel
EXCEL_CONFIG = {
    'filename': 'suppliers_data.xlsx',
    'sheet_name': 'Поставщики',
    'columns': [
        'Название компании',
        'Категория',
        'Подкатегория',
        'Адрес',
        'Телефон',
        'Email',
        'Сайт',
        'Статус',
        'Дата проверки',
        'Примечания'
    ]
}

# Настройки проверки работоспособности
VALIDATION_CONFIG = {
    'check_website': True,
    'check_phone': True,
    'check_email': True,
    'timeout': 10
} 