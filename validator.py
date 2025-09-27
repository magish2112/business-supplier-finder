import requests
import re
import time
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse
from config import VALIDATION_CONFIG
from models import Company, CompanyStatus, ValidationResult

class CompanyValidator:
    """Валидатор для проверки работоспособности компаний"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def validate_company(self, company: Company) -> ValidationResult:
        """Полная валидация компании"""
        result = ValidationResult(company)
        
        # Проверка сайта
        if VALIDATION_CONFIG['check_website'] and company.website:
            result.website_works = self._check_website(company.website)
            
        # Проверка телефона
        if VALIDATION_CONFIG['check_phone'] and company.phone:
            result.phone_works = self._check_phone(company.phone)
            
        # Проверка email
        if VALIDATION_CONFIG['check_email'] and company.email:
            result.email_works = self._check_email(company.email)
            
        # Обновление статуса
        result.update_status()
        
        # Обновление компании
        company.status = result.overall_status
        company.check_date = datetime.now()
        
        return result
    
    def _check_website(self, website: str) -> bool:
        """Проверка работоспособности сайта"""
        try:
            # Добавляем протокол если отсутствует
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website
                
            # Проверяем доступность сайта
            response = self.session.get(
                website, 
                timeout=VALIDATION_CONFIG['timeout'],
                allow_redirects=True
            )
            
            # Проверяем статус код
            if response.status_code == 200:
                # Дополнительная проверка - ищем контактную информацию
                content = response.text.lower()
                contact_indicators = [
                    'контакты', 'связаться', 'телефон', 'email', 'адрес',
                    'contact', 'phone', 'address', 'связь'
                ]
                
                has_contact_info = any(indicator in content for indicator in contact_indicators)
                return has_contact_info
                
        except Exception as e:
            print(f"Ошибка при проверке сайта {website}: {e}")
            
        return False
    
    def _check_phone(self, phone: str) -> bool:
        """Проверка корректности телефона"""
        try:
            # Очищаем номер от лишних символов
            clean_phone = re.sub(r'[^\d+]', '', phone)
            
            # Проверяем формат российского номера
            if clean_phone.startswith('+7') and len(clean_phone) == 12:
                return True
            elif clean_phone.startswith('8') and len(clean_phone) == 11:
                return True
            elif clean_phone.startswith('7') and len(clean_phone) == 11:
                return True
                
        except Exception as e:
            print(f"Ошибка при проверке телефона {phone}: {e}")
            
        return False
    
    def _check_email(self, email: str) -> bool:
        """Проверка корректности email"""
        try:
            # Простая проверка формата email
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(email_pattern, email))
            
        except Exception as e:
            print(f"Ошибка при проверке email {email}: {e}")
            
        return False
    
    def validate_batch(self, companies: list) -> list:
        """Валидация списка компаний"""
        validated_companies = []
        
        for i, company in enumerate(companies):
            print(f"Валидация компании {i+1}/{len(companies)}: {company.name}")
            
            result = self.validate_company(company)
            validated_companies.append(company)
            
            # Небольшая задержка между запросами
            time.sleep(1)
            
        return validated_companies
    
    def get_validation_summary(self, companies: list) -> dict:
        """Получение сводки по валидации"""
        total = len(companies)
        active = sum(1 for c in companies if c.status == CompanyStatus.ACTIVE)
        inactive = sum(1 for c in companies if c.status == CompanyStatus.INACTIVE)
        unknown = sum(1 for c in companies if c.status == CompanyStatus.UNKNOWN)
        
        return {
            'total': total,
            'active': active,
            'inactive': inactive,
            'unknown': unknown,
            'active_percentage': (active / total * 100) if total > 0 else 0
        } 