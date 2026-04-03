from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

_PRICE_QUANTIZE_STEP = Decimal("0.01")
_JUNK_PRICE_VALUES = {"", "-", "n/a", "na", "none", "null"}


def normalize_price_to_decimal(raw: Any) -> Decimal | None:
    """Нормализует цену к Decimal(2) или возвращает None для мусорных значений."""
    if raw is None:
        return None

    text = str(raw).strip().lower().replace("\xa0", " ")
    if text in _JUNK_PRICE_VALUES:
        return None

    text = re.sub(r"[^\d,.-]", "", text.replace(" ", ""))
    if text in _JUNK_PRICE_VALUES or text in {"-", ".", ",", "-.", "-,"}:
        return None

    # AI-note: выбран алгоритм с определением последнего разделителя как десятичного,
    # т.к. он устойчив к форматам типа "1,234.56" и "1.234,56" в данных разных источников.
    if "," in text and "." in text:
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
    else:
        text = text.replace(",", ".")

    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None

    if not value.is_finite() or value <= 0:
        return None

    return value.quantize(_PRICE_QUANTIZE_STEP, rounding=ROUND_HALF_UP)


class RawProductDTO(BaseModel):
    """Сырая модель товара из парсера до строгой валидации полей."""

    model_config = ConfigDict(extra="ignore")

    name: Any
    brand: Any = None
    price: Any
    source: Any
    url: str | None = None
    category: str | None = None


class CleanProductDTO(BaseModel):
    """Очищенная модель товара в едином контракте API/сервиса."""

    model_config = ConfigDict(extra="ignore")

    name: str
    brand: str | None = None
    price: Decimal
    source: str
    url: str | None = None
    category: str | None = None

    @field_validator("name", "source", mode="before")
    @classmethod
    def _validate_required_text(cls, value: Any) -> str:
        text = str(value).strip() if value is not None else ""
        if not text:
            msg = "Поле обязательно и не может быть пустым"
            raise ValueError(msg)
        return text

    @field_validator("brand", mode="before")
    @classmethod
    def _normalize_brand(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("price", mode="before")
    @classmethod
    def _normalize_price(cls, value: Any) -> Decimal:
        normalized = normalize_price_to_decimal(value)
        if normalized is None:
            msg = "Некорректная цена"
            raise ValueError(msg)
        return normalized