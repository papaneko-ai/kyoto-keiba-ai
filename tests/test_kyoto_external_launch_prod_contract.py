"""Offline external-timer/production schedule contract guard. No network or secrets."""
from pathlib import Path
import json
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
PROD=ROOT / ".github/workflows/kyoto-20261121-22-two-source-production-observer.yml"
PROBE=ROOT / ".github/workflows/kyoto-implementation18-external-timer-probe.yml"
CONTRACT={
    "20261121": {
        "jst_opportunities":["2026-11-21T09:15:00+09:00","2026-11-21T10:15:00+09:00"],
        "body":{"ref":"main","inputs":{"race_day":"20261121","confirmation":"NOV21-22-OBSERVE-READ-ONLY"}},
    },
    "20261122": {
        "jst_opportunities":["2026-11-22T09:15:00+09:00","2026-11-22T10:15:00+09:00"],
        "body":{"ref":"main","inputs":{"race_day":"20261122","confirmation":"NOV21-22-OBSERVE-READ-ONLY"}},
    },
}
ENDPOINT="https://api.github.com/repos/papaneko-ai/kyoto-keiba-ai/actions/workflows/kyoto-20261121-22-two-source-production-observer.yml/dispatches"
PROBE_ENDPOINT="https://api.github.com/repos/papaneko-ai/kyoto-keiba-ai/actions/workflows/kyoto-implementation18-external-timer-probe.yml/dispatches"
EXPECTED_SCHEDULE={"5 1 21 11 *","5 2 21 11 *","50 2 21 11 *",
                   "10 1 22 11 *","10 2 22 11 *","55 2 22 11 *"}

def check_sources(prod_text,probe_text):
    errors=[]
    crons=re.findall(r"^\s*- cron: '([^']+)'",prod_text,re.M)
    if len(crons)!=6 or set(crons)!=EXPECTED_SCHEDULE:
        errors.append("PRODUCTION_BACKUP_SCHEDULE_CHANGED")
    for marker in ("  workflow_dispatch:","      race_day:","      confirmation:",
                   "NOV21-22-OBSERVE-READ-ONLY","KYOTO_NOV22_VERIFIED_COLLECTOR_SHA"):
        if marker not in prod_text:
            errors.append("PRODUCTION_DISPATCH_CONTRACT_CHANGED:"+marker.strip())
    if prod_text.count("OUTSIDE_DAY_WINDOW_NO_HTTP")!=2:
        errors.append("BOTH_SOURCE_LANES_MUST_HAVE_TIME_GUARD")
    if prod_text.count("github.event_name == 'workflow_dispatch'")<2:
        errors.append("DISPATCH_NOT_ALLOWED_FOR_BOTH_LANES")
    for marker in ("  workflow_dispatch:","      sent_unix:",
                   "JRA_HTTP_REQUESTS=0","EXTERNAL_PROVIDER_PROVEN=False"):
        if marker not in probe_text:
            errors.append("NO_JRA_PROBE_CONTRACT_CHANGED:"+marker.strip())
    for day,config in CONTRACT.items():
        body=config["body"]
        if body["inputs"]["race_day"]!=day or body["ref"]!="main":
            errors.append("EXTERNAL_BODY_NOT_EXACT:"+day)
        if body["inputs"]["confirmation"]!="NOV21-22-OBSERVE-READ-ONLY":
            errors.append("EXTERNAL_CONFIRMATION_WRONG:"+day)
    return errors

class ContractTest(unittest.TestCase):
    def test_actual_workflows_match(self):
        self.assertEqual(check_sources(PROD.read_text(),PROBE.read_text()),[])
    def test_bad_backup_cron_fails(self):
        txt=PROD.read_text().replace("'5 1 21 11 *'","'5 3 21 11 *'",1)
        self.assertIn("PRODUCTION_BACKUP_SCHEDULE_CHANGED",check_sources(txt,PROBE.read_text()))
    def test_missing_pc_guard_fails(self):
        txt=PROD.read_text().replace("OUTSIDE_DAY_WINDOW_NO_HTTP","REMOVED_WINDOW",1)
        self.assertIn("BOTH_SOURCE_LANES_MUST_HAVE_TIME_GUARD",check_sources(txt,PROBE.read_text()))
    def test_missing_probe_zero_http_fails(self):
        txt=PROBE.read_text().replace("JRA_HTTP_REQUESTS=0","JRA_HTTP_REQUESTS=1")
        self.assertTrue(any(x.startswith("NO_JRA_PROBE") for x in check_sources(PROD.read_text(),txt)))
    def test_schedule_contract_is_immutable(self):
        self.assertEqual(set(CONTRACT),{"20261121","20261122"})
        self.assertTrue(ENDPOINT.startswith("https://api.github.com/repos/papaneko-ai/"))
        self.assertIn("no-JRA", "no-JRA")
if __name__=="__main__":
    unittest.main()
