"""Minimal external timer to GitHub dispatch contract. No network or secrets."""
import json
WORKFLOW = "kyoto-20261121-22-two-source-production-observer.yml"
CONFIRM = "NOV21-22-OBSERVE-READ-ONLY"
DAYS = ("20261121", "20261122")
PATH = "/repos/papaneko-ai/kyoto-keiba-ai/actions/workflows/" + WORKFLOW + "/dispatches"
def payload(day):
    if day not in DAYS:
        raise ValueError("invalid race day")
    return json.dumps({"ref":"main","inputs":{"race_day":day,"confirmation":CONFIRM}},sort_keys=True,separators=(",",":")).encode()
