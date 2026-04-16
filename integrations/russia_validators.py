"""
Валидация и нормализация российских контактных данных (ИНН, телефон, email).
"""

from __future__ import annotations

import re
from typing import Optional

_INN_DIGITS_RE = re.compile(r"^\d{10}$|^\d{12}$")
_EMAIL_BASIC_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def _inn_checksum_10(inn: str) -> bool:
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    s = sum(int(inn[i]) * weights[i] for i in range(9))
    c = s % 11
    if c == 10:
        c = 0
    return c == int(inn[9])


def _inn_checksum_12(inn: str) -> bool:
    w11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    c11 = sum(int(inn[i]) * w11[i] for i in range(10)) % 11
    if c11 == 10:
        c11 = 0
    if c11 != int(inn[10]):
        return False
    w12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    c12 = sum(int(inn[i]) * w12[i] for i in range(11)) % 11
    if c12 == 10:
        c12 = 0
    return c12 == int(inn[11])


def validate_inn(inn: str) -> bool:
    """
    Проверка контрольных цифр ИНН юрлица (10) или физлица (12) по стандартному алгоритму ФНС.
    """
    if not inn or not isinstance(inn, str):
        return False
    digits = re.sub(r"\D", "", inn.strip())
    if not _INN_DIGITS_RE.match(digits):
        return False
    if len(digits) == 10:
        return _inn_checksum_10(digits)
    return _inn_checksum_12(digits)


def normalize_phone_ru(phone: Optional[str]) -> Optional[str]:
    """
    Нормализация российского номера в вид +7XXXXXXXXXX (10 цифр после кода страны) или None.
    """
    if phone is None:
        return None
    s = str(phone).strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    if len(digits) == 11 and digits[0] == "8":
        rest = digits[1:]
        if len(rest) == 10:
            return "+7" + rest
        return None
    if len(digits) == 11 and digits[0] == "7":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        return "+7" + digits
    if len(digits) == 11 and digits.startswith("79"):
        return "+" + digits
    return None


def validate_email_basic(email: Optional[str]) -> bool:
    """Простая проверка формата email (без полной RFC)."""
    if not email or not isinstance(email, str):
        return False
    e = email.strip()
    if not e or ".." in e or e.startswith(".") or e.endswith("."):
        return False
    if "@" not in e or e.count("@") != 1:
        return False
    return bool(_EMAIL_BASIC_RE.match(e))
