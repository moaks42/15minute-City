"""Explanation sentences in pl/cs/en (README §6.3). Always rendered from RAW values — never invented."""
from __future__ import annotations

import math

NBSP = " "


def fmt_number(value: float, lang: str, decimals: int = 0) -> str:
    """Locale formatting mirroring Intl.NumberFormat: pl "12 450" (groups from 5 digits), cs "1 250", en "12,450"."""
    v = round(float(value), decimals)
    if decimals == 0:
        v = int(v)
    s = f"{v:,.{decimals}f}" if decimals else f"{v:,}"
    if lang == "en":
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


def indicator_text(spec, value: float, lang: str) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return render(spec.explain[lang], value=fmt_number(value, lang, spec.decimals))
