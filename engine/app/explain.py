"""Explanation sentences in pl/cs/en/ko (README §6.3). Always rendered from RAW values — never invented."""
from __future__ import annotations

import math

NBSP = " "


def fmt_number(value: float, lang: str, decimals: int = 0) -> str:
    """Locale formatting mirroring Intl.NumberFormat: pl "12 450" (groups from 5 digits), cs "1 250", en/ko "12,450"."""
    v = round(float(value), decimals)
    if decimals == 0:
        v = int(v)
    s = f"{v:,.{decimals}f}" if decimals else f"{v:,}"
    if lang in ("en", "ko"):
        return s
    int_part, _, dec_part = s.partition(".")
    digits = int_part.replace(",", "")
    min_group = 5 if lang == "pl" else 4
    int_out = int_part.replace(",", NBSP) if len(digits.lstrip("-")) >= min_group else digits
    return int_out + ("," + dec_part if dec_part else "")


def render(template: str, **values) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def display_value(value: float, unit: str, lang: str, decimals: int = 0) -> str:
    """Number as shown in a sentence; walk/commute minutes below 1 read "<1" rather than "0"."""
    if unit == "min" and value < 1:
        return "<1"
    return fmt_number(value, lang, decimals)


def indicator_text(spec, value: float, lang: str) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return render(spec.explain[lang], value=display_value(value, spec.unit, lang, spec.decimals))
