"""Shared accent-insensitive matching and exact money helpers."""

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal


def normalize(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize(text))


def to_cents(value: str | Decimal) -> int:
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Money must be finite, nonnegative and have at most two decimals")
    return int(amount * 100)


def discounted(cents: int, percent: int) -> int:
    return int((Decimal(cents) * (100 - percent) / 100).quantize(Decimal(1), ROUND_HALF_UP))


def brl(cents: int) -> str:
    return f"R$ {cents / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
