"""P8 remote deployed *shadow* Streamlit app acceptance, no JRA requests.

Run manually after separately deploying the new shadow app on Streamlit
Community Cloud. A healthy URL is not proof of controlled Cloud reboot or
account billing. The receipt cannot award P8-04 alone.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from urllib.parse import urlsplit
from pathlib import Path

def validate_target(url,expected_sha):
    if type(url) is not str or type(expected_sha) is not str:
        raise ValueError("explicit_url_and_git_sha_required")
    p=urlsplit(url)
    host=p.hostname
    if (p.scheme!="https" or not host or
        (host!="streamlit.app" and not host.endswith(".streamlit.app")) or
        p.port is not None or p.username or p.password or p.query or p.fragment
        or p.path not in ("","/")):
        raise ValueError("only_explicit_https_streamlit_public_app_allowed")
    if re.fullmatch("[0-9a-f]{40}",expected_sha) is None:
        raise ValueError("real_40_character_expected_sha_required")
    return p.geturl().rstrip("/")

def probe_public_shadow_app(*,url,expected_sha,output):
    from playwright.sync_api import sync_playwright
    target=validate_target(url,expected_sha)
    banned=["jra.go.jp","sp.jra.jp","netkeiba.com","www.netkeiba.com"]
    observations=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            for cycle in range(2):
                context=browser.new_context(viewport={"width":390,"height":844},
                                    is_mobile=True,has_touch=True,
                                    device_scale_factor=2)
                try:
                    blocked=[]
                    def route_check(route):
                        hostname=urlsplit(route.request.url).hostname or ""
                        if hostname in banned or hostname.endswith(".jra.go.jp"):
                            blocked.append(hostname)
                            return route.abort()
                        return route.continue_()
                    context.route("**/*",route_check)
                    page=context.new_page()
                    browser_events={"console_errors":[],"page_errors":[],"failed_requests":[],"bad_http_responses":[],"websockets":[],"websocket_events":[]}
                    page.on("console",lambda m: browser_events["console_errors"].append(m.text[:250])
                            if m.type=="error" else None)
                    page.on("pageerror",lambda e: browser_events["page_errors"].append(str(e)[:250]))
                    page.on("requestfailed",lambda r: browser_events["failed_requests"].append({
                        "type":r.resource_type,"origin":urlsplit(r.url).hostname,
                        "failure":r.failure[:160] if r.failure else None}))
                    def ws_trace(ws):
                        safe={"origin":urlsplit(ws.url).hostname,"path":urlsplit(ws.url).path[:100]}
                        browser_events["websockets"].append(safe)
                        ws.on("close",lambda : browser_events["websocket_events"].append({"event":"close",**safe}))
                        ws.on("socketerror",lambda err: browser_events["websocket_events"].append({
                            "event":"socketerror","detail":str(err)[:160],**safe}))
                        # Count frame activity without storing frame payloads, which
                        # may contain source content or personally sensitive values.
                        ws.on("framereceived",lambda frame: browser_events["websocket_events"].append({
                            "event":"frame_received","bytes":len(frame)}) if len(browser_events["websocket_events"]) < 12 else None)
                        ws.on("framesent",lambda frame: browser_events["websocket_events"].append({
                            "event":"frame_sent","bytes":len(frame)}) if len(browser_events["websocket_events"]) < 12 else None)
                    page.on("websocket",ws_trace)
                    def http_trace(resp):
                        if resp.status >= 400:
                            parts=urlsplit(resp.url)
                            browser_events["bad_http_responses"].append({
                                "status":resp.status,"origin":parts.hostname,
                                "path":parts.path[:140],"resource":resp.request.resource_type})
                    page.on("response",http_trace)
                    response=page.goto(target,wait_until="domcontentloaded",timeout=50000)
                    # Community Cloud embeds the actual Streamlit app in a
                    # same-origin /~/+/ frame. The parent page is only a shell.
                    # Inspect the frame instead of weakening the visual checks.
                    app_frame=None
                    for _ in range(40):
                        app_frame=next((fr for fr in page.frames
                            if urlsplit(fr.url).hostname==urlsplit(target).hostname
                            and urlsplit(fr.url).path.startswith("/~/+/")),None)
                        if app_frame is not None:
                            break
                        page.wait_for_timeout(500)
                    if app_frame is None:
                        raise AssertionError("same_origin_streamlit_app_frame_missing")
                    # Do not conceal a remote/cloud failure as a mere missing label.
                    # Record only PUBLIC page diagnostics, never upload contents or secrets.
                    try:
                        app_frame.get_by_text("京都競馬AI｜保存原本の研究用再現").wait_for(timeout=55000)
                    except Exception as exc:
                        from playwright.sync_api import TimeoutError as PlaywrightTimeout
                        if not isinstance(exc,PlaywrightTimeout):
                            raise
                        status = response.status if response is not None else None
                        title = page.title()[:180]
                        current_url = page.url[:250]
                        public_text = app_frame.locator("body").inner_text(timeout=4000)[:600]
                        try:
                            page.screenshot(path="/tmp/kyoto-p8-external-failure-%d.png" % (cycle+1),
                                            full_page=False,timeout=4000)
                        except Exception:
                            pass
                        print("KYOTO_P8_REMOTE_FAILURE_DIAGNOSTIC="+json.dumps({
                            "cycle":cycle+1,"http_status":status,
                            "page_title":title,"observed_url":current_url,
                            "public_body_excerpt":public_text,
                            "browser_events":{k:v[:8] for k,v in browser_events.items()},
                            "streamlit_mount_count":page.locator('[data-testid="stApp"]').count(),
                            "frame_inventory":[{
                                "host":urlsplit(fr.url).hostname,
                                "path":urlsplit(fr.url).path[:100],
                                "app_mount_count":fr.locator('[data-testid="stApp"]').count(),
                                "title_marker_count":fr.get_by_text("京都競馬AI｜保存原本の研究用再現").count()
                            } for fr in page.frames[:6]],
                            "document_ready_state":page.evaluate("document.readyState"),
                            "root_element_count":page.locator("body *").count()
                        },ensure_ascii=False),flush=True)
                        # Independent diagnostic only: compare non-mobile browser.
                        # NEVER convert a desktop result into a mobile PASS.
                        desktop_diagnostic={"rendered":False}
                        try:
                            dc=browser.new_context(viewport={"width":1280,"height":800},
                                                   is_mobile=False,has_touch=False)
                            try:
                                dc.route("**/*",route_check)
                                dp=dc.new_page()
                                dr=dp.goto(target,wait_until="domcontentloaded",timeout=25000)
                                try:
                                    dp.get_by_text("京都競馬AI｜保存原本の研究用再現").wait_for(timeout=22000)
                                    desktop_diagnostic["rendered"]=True
                                except Exception as diagnostic_exc:
                                    from playwright.sync_api import TimeoutError as PWTimeout
                                    if not isinstance(diagnostic_exc,PWTimeout):
                                        raise
                                desktop_diagnostic["http_status"]=dr.status if dr else None
                                desktop_diagnostic["app_mount_count"]=dp.locator('[data-testid="stApp"]').count()
                                desktop_diagnostic["body_characters"]=len(dp.locator("body").inner_text())
                            finally:
                                dc.close()
                        except Exception as diagnostic_exc:
                            desktop_diagnostic["failure_type"]=type(diagnostic_exc).__name__
                        print("KYOTO_P8_DESKTOP_CONTROL="+json.dumps(desktop_diagnostic,sort_keys=True),flush=True)
                        raise AssertionError("public_streamlit_research_heading_not_rendered") from exc
                    app_frame.get_by_text("研究・診断専用。公式データの真正性",exact=False).wait_for(timeout=12000)
                    sha_label="起動コードのGitHubコミット: "+expected_sha
                    if app_frame.get_by_text(sha_label,exact=True).count()!=1:
                        raise AssertionError("deployed_git_sha_not_equal_to_expected")
                    assert response is not None and response.status==200
                    assert app_frame.get_by_role("button",name="研究用に原本から再現").is_disabled()
                    assert app_frame.get_by_text("別途保存された原本ZIPのSHA256",exact=False).count()>0
                    assert app_frame.locator('button:has-text("購入")').count()==0
                    assert app_frame.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
                    assert not blocked,"forbidden_jra_browser_call"
                    observations.append({
                       "cycle":cycle+1,"http_status":response.status,
                       "git_sha_matches":True,"read_only_missing_input_guard":True,
                       "mobile_viewport":390,"no_horizontal_overflow":True,
                       "no_jra_browser_requests":True,"no_betting_control":True})
                finally:
                    context.close()
        finally:
            browser.close()
    body={
       "schema":"kyoto_p8_remote_cloud_shadow_observation.v1",
       "public_url":target,"expected_sha":expected_sha,
       "observations":observations,"public_shadow_deployment_git_sha_verified":True,
       "fresh_browser_sessions":2,
       "actual_cloud_instance_reboot_verified":False,
       "cloud_billing_and_free_tier_account_verified":False,
       "official_jra_market_verified":False,
       "real_racing_prediction_verified":False,
       "P8_04_full_release_certified":False,
       "actual_purchase_authorized":False}
    raw=json.dumps(body,ensure_ascii=False,sort_keys=True,
                   separators=(",",":"),allow_nan=False)
    receipt={**body,"receipt_sha256":hashlib.sha256(raw.encode()).hexdigest()}
    Path(output).write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print("KYOTO_P8_NEW_PUBLIC_DEPLOY_SOURCE_VERIFIED=TRUE")
    print("KYOTO_P8_04_REBOOT_AND_BILLING_VERIFIED=FALSE")
    print("KYOTO_P8_REMOTE_PROBE_SHA256="+receipt["receipt_sha256"])
    return receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--url",required=True)
    p.add_argument("--sha",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    probe_public_shadow_app(url=a.url,expected_sha=a.sha,output=a.out)

if __name__=="__main__":main()
