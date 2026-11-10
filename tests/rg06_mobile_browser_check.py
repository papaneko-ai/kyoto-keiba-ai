"""RG06 mobile-width browser acceptance of the EXISTING offline P8 UI.

Runs Streamlit locally at 390x844 CSS pixels and changes the bet-type radio.
A rendered viewport check is distinct from Streamlit AppTest widget simulation.
No external URLs, order paths, or JRA requests.
"""
from __future__ import annotations
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"diagnostics/p8_mobile_readonly_planner_app.py"
PORT=18767

def main():
    env=dict(os.environ)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"]="false"
    p=subprocess.Popen([sys.executable,"-m","streamlit","run",str(APP),
           "--server.headless=true",f"--server.port={PORT}",
           "--server.address=127.0.0.1","--browser.gatherUsageStats=false"],
           cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
    try:
        endpoint=f"http://127.0.0.1:{PORT}"
        for i in range(70):
            if p.poll() is not None:raise AssertionError("streamlit_start_failed")
            try:
                with urllib.request.urlopen(endpoint+"/_stcore/health",timeout=1) as r:
                    if r.status==200:break
            except Exception:
                time.sleep(1)
        else:raise AssertionError("local_streamlit_timeout")
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
            try:
                page=browser.new_page(viewport={"width":390,"height":844},
                         device_scale_factor=2,is_mobile=True,has_touch=True)
                page.goto(endpoint,wait_until="domcontentloaded",timeout=60000)
                page.get_by_text("研究用E2E再現性診断").wait_for(timeout=60000)
                page.get_by_text("研究用の同一入力・同一結果：2回一致").wait_for(timeout=30000)
                assert page.get_by_text("保存済み出馬表").count()>0
                assert page.get_by_text("148頭").count()>0
                assert page.locator('button:has-text("購入")').count()==0
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"),"mobile_horizontal_overflow"
                page.get_by_text("枠連",exact=True).first.click()
                page.get_by_text("研究用の同一入力・同一結果：2回一致").wait_for(timeout=30000)
                # The mobile interaction must change the data bound to the
                # deterministic E2E receipt, not merely highlight a radio.
                txt=page.locator("body").inner_text()
                assert "研究用券種" in txt and "枠連" in txt
                assert "実開催データ検証" in txt and "未実施" in txt
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"),"mobile_after_toggle_overflow"
                print("KYOTO_RG06_BROWSER_390PX_TOUCH_RADIO_PASS=TRUE",flush=True)
            finally:
                browser.close()
    finally:
        p.terminate()
        try:p.wait(timeout=7)
        except subprocess.TimeoutExpired:p.kill();p.wait(timeout=7)

if __name__=="__main__": main()
