"""Тесты integrations.russia_validators."""

import pytest

from integrations.russia_validators import (
    normalize_phone_ru,
    validate_email_basic,
    validate_inn,
)


def test_validate_inn_10_valid_known():
    assert validate_inn("7707083893")
    assert validate_inn(" 7707-083-893 ")


def test_validate_inn_10_invalid_checksum():
    assert not validate_inn("7707083894")


def test_validate_inn_12_valid_generated():
    # Контрольные цифры по тому же алгоритму, что в модуле
    assert validate_inn("873603741963")


def test_validate_inn_wrong_length():
    assert not validate_inn("123")
    assert not validate_inn("")
    assert not validate_inn(None)  # type: ignore[arg-type]


def test_normalize_phone_ru_variants():
    assert normalize_phone_ru("8 (912) 345-67-89") == "+79123456789"
    assert normalize_phone_ru("+7 912 345 67 89") == "+79123456789"
    assert normalize_phone_ru("9123456789") == "+79123456789"
    assert normalize_phone_ru("79123456789") == "+79123456789"


def test_normalize_phone_ru_invalid():
    assert normalize_phone_ru("") is None
    assert normalize_phone_ru(None) is None
    assert normalize_phone_ru("123") is None


def test_validate_email_basic():
    assert validate_email_basic("user@example.com")
    assert validate_email_basic("  a.b+c@sub.co.uk  ")
    assert not validate_email_basic("bad")
    assert not validate_email_basic("@no.local")
    assert not validate_email_basic("")
    assert not validate_email_basic(None)  # type: ignore[arg-type]
