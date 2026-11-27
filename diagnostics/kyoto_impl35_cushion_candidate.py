"""Isolated supplementary cushion candidate, not official or production input.
Only observed public TURF SCOPE links. No network calls or guessed identifiers.
HTML structure is based on visible source fields, not verified raw-source fixtures.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

INDEX = "https://keiba-win-net.com/updates/track"
JST = timezone(timedelta(hours=9))
UTC = timezone.utc
WEEK = "月火水木金土日"
MAX_BYTES = 2_000_000

class Rejected(ValueError):
    pass

def norm(s):
    return " ".join(unicodedata.normalize("NFKC", s).split())

class Visible(HTMLParser):
    def __init__(self, raw):
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
            raise Rejected("raw_size")
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.anchor = [], [], None
        self.skip = 0
        self.feed(raw.decode("utf-8-sig", errors="strict"))
        self.close()
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self.skip += 1
        if not self.skip and tag == "a":
            self.anchor = [dict(attrs).get("href") or "", []]
    def handle_endtag(self, tag):
        if tag in ("script", "style", "template") and self.skip:
            self.skip -= 1
        if not self.skip and tag == "a" and self.anchor is not None:
            self.links.append((self.anchor[0], norm(" ".join(self.anchor[1]))))
            self.anchor = None
    def handle_data(self, s):
        if self.skip:
            return
        self.parts.append(s)
        if self.anchor is not None:
            self.anchor[1].append(s)

def valid_detail(url):
    u = urlsplit(url)
    return (u.scheme == "https" and u.netloc == "keiba-win-net.com"
            and not u.query and not u.fragment
            and re.fullmatch(r"/updates/[0-9a-f]{64}", u.path) is not None)

def day_value(day):
    if not re.fullmatch(r"\d{8}", day):
        raise Rejected("target_date")
    return datetime.strptime(day, "%Y%m%d").date()

def day_label(day):
    d = day_value(day)
    return rf"{d.month}月{d.day}日\s*\({WEEK[d.weekday()]}曜\)"

def observed_links(raw, day, index_url=INDEX):
    if index_url != INDEX:
        raise Rejected("index_identity")
    label = day_label(day)
    pattern = rf"京都\s+{label}\s*\d{{1,2}}時\d{{2}}分\s+クッション値\s+\d+(?:\.\d+)?"
    out = set()
    for href, title in Visible(raw).links:
        if re.fullmatch(pattern, title):
            url = urljoin(index_url, href)
            if valid_detail(url):
                out.add(url)
    return sorted(out)

def unique(pattern, text, error):
    values = set(re.findall(pattern, text))
    if len(values) != 1:
        raise Rejected(error)
    return values.pop()

def aware_utc(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.utcoffset() != timedelta(0):
        raise Rejected("capture_not_utc")
    return t.astimezone(UTC)

def parse_detail(raw, day, url, captured_at_utc, cutoff_utc=None):
    if not valid_detail(url):
        raise Rejected("source_identity")
    d = day_value(day)
    v = Visible(raw)
    text = norm(" ".join(v.parts))
    label = day_label(day)
    h, m, number = unique(
        rf"京都\s+{label}\s*(\d{{1,2}})時(\d{{2}})分\s+クッション値\s+(\d+(?:\.\d+)?)(?![\d.])",
        text, "heading_identity_or_conflict")
    venue = unique(r"競馬場\s+(京都|東京|福島|阪神|中山|中京|小倉|札幌|函館|新潟)(?=\s|$)", text, "venue")
    value = unique(r"クッション値\s+(\d+(?:\.\d+)?)\s+測定日時の原表記", text, "value_field")
    mh, mm = unique(rf"測定日時の原表記\s+{label}\s*(\d{{1,2}})時(\d{{2}})分", text, "measurement_field")
    if venue != "京都" or (h, m) != (mh, mm) or Decimal(number) != Decimal(value):
        raise Rejected("field_conflict")
    amount = Decimal(value)
    if not Decimal(0) < amount <= Decimal(100):
        raise Rejected("value_range")
    observed = unique(r"初回取得(?:\s*[:：]\s*|\s+)(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s*\(日本時間\)", text, "provider_observed")
    first = datetime.strptime(observed, "%Y/%m/%d %H:%M:%S").replace(tzinfo=JST).astimezone(UTC)
    measured = datetime(d.year, d.month, d.day, int(h), int(m), tzinfo=JST).astimezone(UTC)
    capture = aware_utc(captured_at_utc)
    if not measured <= first <= capture or first.astimezone(JST).date() not in (d, d + timedelta(days=1)):
        raise Rejected("time_order")
    originals = sorted({href for href, _ in v.links
                        if urlsplit(href).scheme == "https"
                        and urlsplit(href).netloc in ("www.jra.go.jp", "jra.jp", "www.jra.jp")})
    if not originals:
        raise Rejected("missing_official_reference")
    cutoff = aware_utc(cutoff_utc) if cutoff_utc is not None else None
    return {
        "schema": "kyoto_impl35_cushion_candidate.v1",
        "day": day, "venue": venue, "source_url": url,
        "source_sha256": sha256(raw).hexdigest(), "bytes": len(raw),
        "cushion_value": format(amount.normalize(), "f"),
        "measurement_utc": measured.isoformat(),
        "provider_first_observed_utc": first.isoformat(),
        "captured_at_utc": capture.isoformat(),
        "capture_before_cutoff": capture < cutoff if cutoff else None,
        "official_reference_urls": originals,
        "official_original_verified": False,
        "official_publication_time_verified": False,
        "prediction_ready": False,
        "state": "SUPPLEMENTARY_CANDIDATE_ONLY",
    }
