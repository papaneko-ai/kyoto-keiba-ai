"""P8-04 local Streamlit deployment and restart-recovery acceptance.

Runs the isolated research shadow app as two fresh processes (same port), on
a 390 CSS-pixel mobile Chromium viewport. Denies external browser traffic.
Evidence is *local GitHub runner only*, never remote Streamlit Cloud proof,
never real JRA origin, and never proof that a paid service has no fees.
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"diagnostics/p8_uploaded_archive_shadow_app.py"
PORT=18872

def _health(process,endpoint):
    for _ in range(75):
        if process.poll() is not None:
            raise AssertionError("p8_04_server_terminated_early")
        try:
            with urllib.request.urlopen(endpoint+"/_stcore/health",timeout=1) as response:
                if response.status==200:
                    return
        except Exception:
            time.sleep(1)
    raise AssertionError("p8_04_local_server_not_ready")

def _boot_and_check(browser,round_num):
    env=dict(os.environ)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"]="false"
    env["STREAMLIT_SERVER_HEADLESS"]="true"
    env["PYTHONPATH"]=str(ROOT)
    endpoint=f"http://127.0.0.1:{PORT}"
    command=[sys.executable,"-m","streamlit","run",str(APP),
             "--server.headless=true","--server.address=127.0.0.1",
             f"--server.port={PORT}","--browser.gatherUsageStats=false",
             "--server.fileWatcherType=none"]
    with tempfile.TemporaryFile() as log:
        p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                           env=env,cwd=ROOT)
        try:
            _health(p,endpoint)
            context=browser.new_context(viewport={"width":390,"height":844},
                   device_scale_factor=2,is_mobile=True,has_touch=True)
            try:
                blocked_external=[]
                def route_request(route):
                    url=route.request.url
                    if url.startswith(endpoint+"/") or url==endpoint:
                        route.continue_()
                    else:
                        blocked_external.append(url.split("?")[0][:160])
                        route.abort()
                context.route("**/*",route_request)
                page=context.new_page()
                page.goto(endpoint,wait_until="domcontentloaded",timeout=60000)
                page.get_by_text("京都競馬AI｜保存原本の研究用再現").wait_for(timeout=60000)
                page.get_by_text("研究・診断専用。公式データの真正性",exact=False).wait_for(timeout=30000)
                button=page.get_by_role("button",name="研究用に原本から再現")
                button.wait_for(timeout=30000)
                assert button.is_disabled(),"no_data_must_fail_closed"
                assert page.get_by_text("別途保存された原本ZIPのSHA256",exact=False).count()>0
                assert page.get_by_text("研究用・事前固定モデルJSON",exact=False).count()>0
                assert page.get_by_text("券種",exact=True).count()>0
                assert page.get_by_text("馬連",exact=True).count()>0
                assert page.get_by_text("枠連",exact=True).count()>0
                assert page.locator('button:has-text("購入")').count()==0
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"),"mobile_overflow"
                # UI real interaction is tested, not a mock Streamlit widget.
                page.get_by_text("枠連",exact=True).first.click()
                page.get_by_role("button",name="研究用に原本から再現").wait_for(timeout=30000)
                assert button.is_disabled(),"radio_must_not_bypass_input_guard"
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"),"mobile_after_toggle_overflow"
                summary={
                  "title_present":True,"warning_present":True,
                  "separate_sha_required":True,"model_upload_required":True,
                  "missing_upload_button_disabled":True,"mobile_width_css_px":390,
                  "ticket_type_toggle_checked":True,"no_purchase_control":True,
                  "no_mobile_horizontal_overflow":True,
                  "external_browser_requests_blocked_count":len(blocked_external),
                  "external_browser_requests_allowed":0}
                return summary
            finally:
                context.close()
        except Exception:
            log.seek(0)
            print(log.read().decode("utf-8",errors="replace")[-8000:],file=sys.stderr)
            raise
        finally:
            p.terminate()
            try:p.wait(timeout=9)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=9)

def main():
    if not APP.is_file():
        raise AssertionError("independent_shadow_app_missing")
    source_sha=hashlib.sha256(APP.read_bytes()).hexdigest()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            first=_boot_and_check(browser,1)
            second=_boot_and_check(browser,2)
        finally:
            browser.close()
    stable={key:first[key] for key in first if key!="external_browser_requests_blocked_count"}
    repeat={key:second[key] for key in second if key!="external_browser_requests_blocked_count"}
    assert stable==repeat,"restart_changes_visible_controls_or_safety"
    output={
      "schema":"kyoto_p8_local_deployment_restart_receipt.v1",
      "scope":"GITHUB_RUNNER_LOCAL_ONLY_NOT_PUBLISHED_STREAMLIT_CLOUD",
      "source_app":"diagnostics/p8_uploaded_archive_shadow_app.py",
      "source_sha256":source_sha,"restart_cycles":2,
      "same_local_port_reused":True,"same_controls_on_restart":True,
      "checks":stable,
      "external_http_calls_from_backend_authorized":False,
      "external_browser_calls_allowed":0,
      "nonfree_runtime_services_configured":False,
      "actual_cloud_cost_zero_verified":False,
      "actual_public_url_deployed_verified":False,
      "live_jra_market_verified":False,
      "real_paper_trade_verified":False,
      "actual_purchase_authorized":False}
    canonical=json.dumps(output,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
    output["receipt_sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    path=Path(os.environ.get("KYOTO_P8_04_OUT","/tmp/kyoto-p8-local-deployment-restart.json"))
    path.write_text(json.dumps(output,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print("KYOTO_P8_LOCAL_DEPLOY_RESTART_PASS=TRUE")
    print("KYOTO_P8_PUBLIC_CLOUD_VERIFIED=FALSE")
    print("KYOTO_P8_ZERO_CLOUD_COST_VERIFIED=FALSE")
    print("KYOTO_P8_LOCAL_DEPLOY_SHA256="+output["receipt_sha256"])

if __name__=="__main__":main()
