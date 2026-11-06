"""Offline-only JRA runner link candidate extraction. No network, no fabricated IDs."""
from dataclasses import dataclass, asdict
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import json, re

MAX_BYTES = 2_000_000
ACTION = re.compile(r"doAction\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", re.I)
HORSE_ID = re.compile(r"(?:^|[?&])(?:horse_id|horseId|ketto_num|kettonum|bloodnum)=([0-9]{8,12})(?:&|$)", re.I)

@dataclass(frozen=True)
class HorseLinkCandidate:
    label: str
    endpoint: str
    action_token: str | None
    explicit_horse_id: str | None
    identity_status: str
    row_text: str

class RowLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.anchor = None
        self.table_depth = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'table':
            self.table_depth += 1
        if tag == 'tr' and self.table_depth and self.row is None:
            self.row = {'text': [], 'links': []}
        if tag == 'a' and self.row is not None:
            self.anchor = {'label': [], 'onclick': d.get('onclick', ''), 'href': d.get('href', '')}

    def handle_data(self, data):
        if self.row is not None:
            self.row['text'].append(data)
        if self.anchor is not None:
            self.anchor['label'].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor is not None:
            self.anchor['label'] = ' '.join(''.join(self.anchor['label']).split())
            self.row['links'].append(self.anchor)
            self.anchor = None
        if tag == 'tr' and self.row is not None:
            self.row['text'] = ' '.join(''.join(self.row['text']).split())
            self.rows.append(self.row)
            self.row = None
        if tag == 'table' and self.table_depth:
            self.table_depth -= 1

def inspect_html(raw: bytes, *, source_url: str, fetched_at_utc: datetime, race_id: str | None = None) -> dict:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('invalid_html_size')
    if fetched_at_utc.tzinfo is None or fetched_at_utc.utcoffset() is None:
        raise ValueError('utc_timestamp_required')
    if fetched_at_utc.utcoffset().total_seconds() != 0:
        raise ValueError('timestamp_must_be_utc')
    if urlparse(source_url).hostname not in ('www.jra.go.jp', 'jra.go.jp'):
        raise ValueError('non_jra_source')
    p = RowLinkParser()
    p.feed(raw.decode('cp932', errors='replace'))
    found = []
    for row in p.rows:
        for link in row['links']:
            match = ACTION.search(link['onclick'])
            href = link['href']
            token = None
            endpoint = href
            if match and 'accessR.html' in match.group(1):
                endpoint, token = match.groups()
            elif 'horse' not in href.lower() and 'accessR.html' not in href:
                continue
            label = link['label']
            if not label or label in ('競走馬検索', '競走馬登録', '馬名'):
                continue
            explicit = HORSE_ID.search(href)
            horse_id = explicit.group(1) if explicit else None
            found.append(HorseLinkCandidate(label, endpoint, token, horse_id,
                         'EXPLICIT_ID_UNVERIFIED' if horse_id else 'HORSE_ID_UNRESOLVED',
                         row['text'][:240]))
    seen = set()
    distinct = []
    for item in found:
        key = (item.label, item.endpoint, item.action_token)
        if key not in seen:
            distinct.append(asdict(item))
            seen.add(key)
    return {'schema_version': 'offline_runner_probe.v1', 'source_url': source_url,
            'source_sha256': sha256(raw).hexdigest(),
            'fetched_at_utc': fetched_at_utc.isoformat(), 'race_id': race_id,
            'candidate_count': len(distinct), 'candidates': distinct,
            'full_race_verified': False, 'ready_for_model': False,
            'missing_reason': 'racecard_completeness_and_horse_identity_not_verified',
            'scope_warning': 'Links may represent results or a multi-race index; never label as all starters without racecard verification'}

def inspect_file(path: Path, *, source_url: str, fetched_at_utc: datetime, race_id: str | None = None) -> dict:
    return inspect_html(path.read_bytes(), source_url=source_url, fetched_at_utc=fetched_at_utc, race_id=race_id)

def safe_write_report(path: Path, report: dict) -> None:
    if report.get('ready_for_model') is not False:
        raise ValueError('offline_report_must_remain_unverified')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
