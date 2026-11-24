"""Lossless classification for observed JRA pair-market odds cells.

Candidate module. Callers must keep invalid/unavailable cells out of price
calculations and must not claim market completeness solely from this parser.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import unicodedata

CANCELLED = frozenset({"取消", "出走取消", "競走除外", "除外"})
UNAVAILABLE = frozenset({"", "-", "---", "未発売", "発売前", "締切", "発売終了"})

@dataclass(frozen=True)
class OddsCell:
    state: str
    original: str
    odds: Decimal | None

def classify_odds_cell(value: str) -> OddsCell:
    if value is None:
        return OddsCell("INVALID", "", None)
    original = str(value)
    s = re.sub(r"\s+", "", unicodedata.normalize("NFKC", original))
    if s in CANCELLED:
        return OddsCell("CANCELLED", original, None)
    if s in UNAVAILABLE or s in {"—", "−"}:
        return OddsCell("UNAVAILABLE", original, None)
    if not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", s):
        return OddsCell("INVALID", original, None)
    try:
        d = Decimal(s.replace(",", ""))
    except InvalidOperation:
        return OddsCell("INVALID", original, None)
    if not d.is_finite() or d <= 0:
        return OddsCell("INVALID", original, None)
    return OddsCell("VALID", original, d)

def split_market_cells(cells):
    groups = {"VALID": {}, "CANCELLED": {}, "UNAVAILABLE": {}, "INVALID": {}}
    for pair, raw in cells.items():
        cell = classify_odds_cell(raw)
        groups[cell.state][pair] = cell
    return groups
