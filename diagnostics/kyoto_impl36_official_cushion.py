"""Parse only the independently observed JRA official cushion fragment.
Year is inferred from capture proximity and the printed weekday, not asserted
as a separately published field. No network or production write in this module.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
import re

URL = "https://www.jra.go.jp/keiba/baba/_data_cushion.html"
JST = timezone(timedelta(hours=9))
WEEK = "月火水木金土日"
MAX_BYTES = 2_000_000

class Rejected(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise Rejected(reason)

class Fragment(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.roots = []
        self.feed(raw)
        self.close()
        need(not self.stack, "unclosed_div")
    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        need(len(dict(attrs)) == len(attrs), "duplicate_attribute")
        node = {"attrs": dict(attrs), "children": [], "text": []}
        if self.stack:
            self.stack[-1]["children"].append(node)
        else:
            self.roots.append(node)
        self.stack.append(node)
    def handle_endtag(self, tag):
        if tag == "div":
            need(bool(self.stack), "unmatched_div")
            self.stack.pop()
    def handle_data(self, data):
        if self.stack:
            self.stack[-1]["text"].append(data)

def single(nodes, key, value):
    matches = [n for n in nodes if n["attrs"].get(key) == value]
    need(len(matches) == 1, "missing_or_duplicate_" + key)
    return matches[0]

def field(row, name):
    node = single(row["children"], "class", name)
    need(not node["children"], "nested_field")
    return "".join(node["text"]).strip()

def utc(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    need(t.utcoffset() == timedelta(0), "non_utc_capture")
    return t.astimezone(timezone.utc)

def parse_official(raw, day, source_url, captured_at_utc, cutoff_utc=None):
    need(source_url == URL, "source_identity")
    need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "raw_size")
    need(re.fullmatch(r"[0-9]{8}", day) is not None, "target_day")
    target = datetime.strptime(day, "%Y%m%d").date()
    captured = utc(captured_at_utc)
    age = (captured.astimezone(JST).date() - target).days
    need(0 <= age <= 31, "target_outside_recent_window")
    try:
        decoded = raw.decode("utf-8-sig", errors="strict")
        encoding = "utf-8"
    except UnicodeDecodeError:
        decoded = raw.decode("cp932", errors="strict")
        encoding = "cp932"
    root = single(Fragment(decoded).roots, "id", "cushion_data_list")
    venue = single(root["children"], "title", "京都")
    # rcA/B/C are display slots, not permanent venue identifiers.
    found = []
    for row in venue["children"]:
        if row["attrs"].get("class") != "unit":
            continue
        label = field(row, "time")
        m = re.fullmatch(r"([0-9]{1,2})月([0-9]{1,2})日[（(]([月火水木金土日])曜[）)]\s*([0-9]{1,2})時([0-9]{2})分", label)
        need(m is not None, "invalid_measurement_label")
        month, date, weekday, hour, minute = m.groups()
        if (int(month), int(date)) != (target.month, target.day):
            continue
        need(weekday == WEEK[target.weekday()], "weekday_mismatch")
        measured = datetime(target.year, target.month, target.day, int(hour), int(minute), tzinfo=JST).astimezone(timezone.utc)
        need(measured <= captured, "future_measurement")
        val = field(row, "cushion")
        need(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", val) is not None, "invalid_value")
        amount = Decimal(val)
        need(Decimal(0) < amount <= Decimal(100), "value_range")
        found.append((measured, amount, label))
    need(len(found) == 1, "missing_or_duplicate_target")
    measured, amount, label = found[0]
    cutoff = utc(cutoff_utc) if cutoff_utc else None
    return {"schema":"kyoto_impl36_official_cushion.v1","day":day,
            "venue":"京都","source_url":source_url,"encoding":encoding,
            "source_sha256":sha256(raw).hexdigest(),"bytes":len(raw),
            "cushion_value":format(amount.normalize(),"f"),
            "measurement_utc":measured.isoformat(),"measurement_label":label,
            "year_basis":"recent_capture_and_printed_weekday",
            "captured_at_utc":captured.isoformat(),
            "capture_before_cutoff":captured < cutoff if cutoff else None,
            "official_publication_time_verified":False,
            "prediction_ready":False}
