"""Extensible bet-type quote ledger for the Kyoto AI.

Implements AND capability: both quinella and bracket-quinella may be retained
for one race. Trio and trifecta are schema-ready, NOT live-source enabled.
No wagers, inferred odds, modeled probabilities, or implicit conversion.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone
from hashlib import sha256
import re

CAPABILITIES={"quinella":(2,False),"bracket_quinella":(2,False),
              "trio":(3,False),"trifecta":(3,True)}
ACTIVE_MARKETS=frozenset(("quinella","bracket_quinella"))
class MarketQuoteError(ValueError):pass

def _utc(value):
    if not isinstance(value,str):raise MarketQuoteError("utc_required")
    try:dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise MarketQuoteError("bad_utc") from exc
    if dt.tzinfo is None or dt.utcoffset()!=timezone.utc.utcoffset(None):
        raise MarketQuoteError("utc_must_be_aware")
    return dt

def _amount(value):
    if type(value) is not str:raise MarketQuoteError("decimal_string_required")
    try:result=Decimal(value)
    except InvalidOperation as exc:raise MarketQuoteError("non_decimal_odds") from exc
    if not result.is_finite() or result<Decimal("1.0") or result>Decimal("1000000"):
        raise MarketQuoteError("odds_out_of_bounds")
    return result

@dataclass(frozen=True)
class MarketQuote:
    race_id:str
    bet_type:str
    combination:tuple[int,...]
    odds:str
    captured_utc:str
    source_sha256:str
    source_phase:str
    def validated(self, *, cutoff_utc):
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}_KYOTO_(?:[1-9]|1[0-2])R",self.race_id):
            raise MarketQuoteError("race_identity_invalid")
        if self.bet_type not in CAPABILITIES:raise MarketQuoteError("unknown_market")
        size,ordered=CAPABILITIES[self.bet_type]
        nums=self.combination
        if (type(nums) is not tuple or len(nums)!=size or
                any(type(x) is not int or x<1 or x>18 for x in nums) or
                (self.bet_type!="bracket_quinella" and len(set(nums))!=size)):
            raise MarketQuoteError("combination_invalid")
        if not ordered and tuple(sorted(nums))!=nums:
            raise MarketQuoteError("unordered_market_must_be_canonical")
        if self.bet_type=="bracket_quinella" and any(n>8 for n in nums):
            raise MarketQuoteError("frame_range_invalid")
        _amount(self.odds)
        if not re.fullmatch("[0-9a-f]{64}",self.source_sha256):
            raise MarketQuoteError("source_original_hash_required")
        if self.source_phase!="LIVE_PRE_RACE" or not _utc(self.captured_utc)<_utc(cutoff_utc):
            raise MarketQuoteError("no_valid_live_prerace_source")
        return self

def combine_market_quotes(quotes, *, cutoff_utc, authorized_markets=ACTIVE_MARKETS):
    """Retain all independently verified quotes without forcing one market.

    All future-market plugins must be explicitly enabled only once real
    parsing, outcome probability and settlement are independently validated.
    """
    if type(quotes) is not list or not quotes:
        raise MarketQuoteError("quotes_list_required")
    if not set(authorized_markets)<=ACTIVE_MARKETS or not authorized_markets:
        raise MarketQuoteError("unverified_future_market_disabled")
    unique={};race_ids=set();types=set()
    for quote in quotes:
        if not isinstance(quote,MarketQuote):raise MarketQuoteError("quote_type_invalid")
        if quote.bet_type not in authorized_markets:
            raise MarketQuoteError("market_not_currently_enabled")
        quote.validated(cutoff_utc=cutoff_utc)
        key=(quote.bet_type,quote.combination)
        if key in unique:
            raise MarketQuoteError("duplicate_market_combination")
        unique[key]=quote
        race_ids.add(quote.race_id);types.add(quote.bet_type)
    if len(race_ids)!=1:raise MarketQuoteError("different_races_mixed")
    return {"schema":"kyoto_extensible_market_quotes.v1",
            "race_id":next(iter(race_ids)),
            "markets_present":sorted(types),
            "supports_quinella_and_bracket_together":ACTIVE_MARKETS<=types,
            "quotations":sorted(unique.values(),key=lambda x:(x.bet_type,x.combination)),
            "future_types_supported_by_schema":["trio","trifecta"],
            "future_types_prediction_enabled":False,
            "recommendations_ready":False,"automatic_wagering_enabled":False}
