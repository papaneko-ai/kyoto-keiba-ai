"""Read-only check of an EXISTING publicly deployed Streamlit diagnostic.

This never uses JRA or market URLs, never updates Cloud, never uses secrets,
and cannot certify the newly developed P8 shadow app. It produces an
auditable RECEIPT of what GitHub Actions can observe externally.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

BASE="https://kyoto-ai-cloud-probe.streamlit.app"
URLS=[BASE+"/_stcore/health",BASE+"/"]
def check(url):
    started=time.monotonic()
    req=urllib.request.Request(url,headers={
        "User-Agent":"KyotoAICloudReadOnlyVerification/1.0",
        "Accept":"text/html,application/json,text/plain"})
    try:
        with urllib.request.urlopen(req,timeout=15,context=ssl.create_default_context()) as response:
            body=response.read(16384)
            return {"http_status":int(response.status),
                    "body_sha256_prefix16":hashlib.sha256(body).hexdigest()[:16],
                    "content_type":response.headers.get("Content-Type","").split(";")[0],
                    "final_origin_host":urlsplit(response.geturl()).hostname,
                    "duration_ms":round((time.monotonic()-started)*1000)}
    except (OSError,urllib.error.URLError,TimeoutError) as e:
        return {"http_status":None,"error_type":type(e).__name__,
                "duration_ms":round((time.monotonic()-started)*1000)}

def main():
    checks=[{"path":p,"observation":check(BASE+p)} for p in ("/_stcore/health","/")]
    body={"schema":"kyoto_existing_public_cloud_observation.v1",
      "scope":"EXISTING_CLOUD_PROBE_APP_ONLY_NOT_P8_SHADOW",
      "utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "observed_origin":BASE,
      "checks":checks,
      "existing_deployment_health_confirmed":all(
           x["observation"].get("http_status")==200 and
           x["observation"].get("final_origin_host")=="kyoto-ai-cloud-probe.streamlit.app"
           for x in checks),
      "new_P8_shadow_app_publicly_deployed":False,
      "cloud_app_restarted_or_restored":False,
      "cloud_billing_account_verified":False,
      "P8_04_release_certified":False,
      "official_jra_source_verified":False,
      "actual_purchase_authorized":False,
      "external_jra_http_requests":0}
    raw=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    result={**body,"receipt_sha256":hashlib.sha256(raw.encode()).hexdigest()}
    dest=Path(os.environ.get("KYOTO_PUBLIC_PROBE_OUT","/tmp/kyoto-public-probe.json"))
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print("KYOTO_EXISTING_CLOUD_HEALTH_OK="+str(body["existing_deployment_health_confirmed"]).upper())
    print("KYOTO_NEW_P8_SHADOW_PUBLICLY_DEPLOYED=FALSE")
    print("KYOTO_P8_04_PUBLIC_CLOUD_CERTIFIED=FALSE")
    print("KYOTO_EXISTING_CLOUD_RECEIPT_SHA256="+result["receipt_sha256"])

if __name__=="__main__":main()
