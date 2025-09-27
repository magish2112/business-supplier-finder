from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class CompanyStatus(Enum):
    ACTIVE = "Работает"
    INACTIVE = "Не работает"
    UNKNOWN = "Неизвестно"

class CompanyType(Enum):
    PRODUCER = "Производитель"
    DISTRIBUTOR = "Дистрибьютор"
    WHOLESALE_SUPPLIER = "Оптовый поставщик"
    RETAIL_SUPPLIER = "Розничный поставщик"
    WAREHOUSE = "Склад"
    UNKNOWN = "Неизвестно"

class CompanySize(Enum):
    LARGE = "Крупная"
    MEDIUM = "Средняя"
    SMALL = "Маленькая"
    UNKNOWN = "Неизвестно"

@dataclass
class Company:
    """Улучшенная модель компании с типизацией и ранжированием"""
    name: str
    category: str
    subcategory: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    status: CompanyStatus = CompanyStatus.UNKNOWN
    check_date: Optional[datetime] = None
    notes: Optional[str] = None
    source: Optional[str] = None

    # Новые поля для улучшенного ранжирования
    company_type: CompanyType = CompanyType.UNKNOWN
    company_size: CompanySize = CompanySize.UNKNOWN
    relevance_score: int = 0
    business_indicators: List[str] = field(default_factory=list)
    contact_completeness: int = 0  # 0-100, процент заполненности контактов
    last_updated: Optional[datetime] = None

    def calculate_relevance_score(self, search_query: str = "", region: str = "") -> int:
        """Расчет релевантности компании"""
        score = 0
        name_lower = self.name.lower()

        # Базовый балл за наличие названия
        score += 10

        # Бонус за тип компании
        if self.company_type == CompanyType.PRODUCER:
            score += 30
        elif self.company_type == CompanyType.DISTRIBUTOR:
            score += 25
        elif self.company_type == CompanyType.WHOLESALE_SUPPLIER:
            score += 20

        # Бонус за размер компании
        if self.company_size == CompanySize.LARGE:
            score += 15
        elif self.company_size == CompanySize.MEDIUM:
            score += 10

        # Бонус за наличие контактов
        contacts_count = sum([1 for contact in [self.phone, self.email, self.website] if contact])
        score += contacts_count * 5

        # Бонус за полноту контактов
        self.contact_completeness = (contacts_count / 3) * 100
        score += int(self.contact_completeness * 0.3)

        # Бонус за совпадение с поисковым запросом
        if search_query and search_query.lower() in name_lower:
            score += 15

        # Бонус за регион
        if region and region.lower() in str(self.address or '').lower():
            score += 10

        self.relevance_score = score
        return score

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для Excel с дополнительными полями"""
        return {
            'Название компании': self.name,
            'Категория': self.category,
            'Подкатегория': self.subcategory,
            'Тип компании': self.company_type.value,
            'Размер компании': self.company_size.value,
            'Адрес': self.address or '',
            'Телефон': self.phone or '',
            'Email': self.email or '',
            'Сайт': self.website or '',
            'Статус': self.status.value,
            'Дата проверки': self.check_date.strftime('%Y-%m-%d %H:%M:%S') if self.check_date else '',
            'Релевантность': self.relevance_score,
            'Полнота контактов': f"{self.contact_completeness:.1f}%",
            'Бизнес-индикаторы': ', '.join(self.business_indicators),
            'Примечания': self.notes or '',
            'Источник': self.source or '',
            'Последнее обновление': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else ''
        }

@dataclass
class SearchResult:
    """Результат поиска"""
    companies: List[Company]
    total_found: int
    search_query: str
    source: str
    timestamp: datetime

class ValidationResult:
    """Результат валидации компании"""
    def __init__(self, company: Company):
        self.company = company
        self.website_works: bool = False
        self.phone_works: bool = False
        self.email_works: bool = False
        self.overall_status: CompanyStatus = CompanyStatus.UNKNOWN
        
    def update_status(self):
        """Обновление общего статуса на основе проверок"""
        if self.website_works or self.phone_works or self.email_works:
            self.overall_status = CompanyStatus.ACTIVE
        else:
            self.overall_status = CompanyStatus.INACTIVE 