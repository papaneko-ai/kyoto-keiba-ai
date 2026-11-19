"""Isolated cross-environment Streamlit probe; no writes without explicit opt-in.

This is a separate Streamlit entry point, never imported by production app.py.
Only accepts the exact designated non-production Turso database and a run ID.
"""
from __future__ import annotations
import hashlib
import hmac
import re

from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
from diagnostics.kyoto_turso_claim_manual_crossrunner import synthetic_key
from diagnostics.kyoto_turso_isolated_virtual_store import endpoint
from diagnostics.kyoto_shared_capture_reservation import key

EXPECTED_HOST="kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io"
CONFIRM="YES-ISOLATED-STREAMLIT-LAB-ONLY"

def proof_key(run_id: str) -> str:
    if type(run_id) is not str or re.fullmatch(r"[0-9]{8,20}",run_id) is None:
        raise ValueError("invalid_run_id")
    return "lab:"+run_id+":"+key(day="20261121",slot=0,race=1,channel="PC",market="racecard")

def lab_client(url: str,token: str,transport):
    endpoint(url)
    if type(token) is not str or len(token)<16 or any(ch.isspace() for ch in token):
        raise ValueError("lab_token_unavailable")
    return TursoCaptureClaims(url=url,token=token,transport=transport,namespace="ISOLATED_LAB")

def observe_finished_gh_run(service,run_id: str) -> dict:
    k=proof_key(run_id)
    found=service.observe(k)
    if not found or found["state"]!="DONE" or not found.get("receipt_sha256"):
        return {"status":"NOT_VERIFIED","state":"MISSING_OR_UNFINISHED"}
    expected=hashlib.sha256(("SYNTHETIC_NO_JRA:"+k).encode()).hexdigest()
    if not hmac.compare_digest(found["receipt_sha256"],expected):
        return {"status":"NOT_VERIFIED","state":"DIGEST_MISMATCH"}
    if found["owner"] not in ("lab_"+run_id+"_contender_first","lab_"+run_id+"_contender_second"):
        return {"status":"NOT_VERIFIED","state":"UNEXPECTED_OWNER"}
    return {"status":"REMOTE_GITHUB_RECEIPT_OBSERVED","state":"DONE","generation":found["generation"]}

def attempt_active_lease(service,run_id: str,now_epoch: int) -> dict:
    """Explicit write attempt only. Must never claim the lease if it is unheld."""
    k=proof_key(run_id)
    found=service.observe(k)
    expected_owner="lab_"+run_id+"_streamlit_hold"
    if (not found or found["state"]!="LEASED"
        or found["expires_at"]<=now_epoch
        or found["owner"]!=expected_owner):
        return {"status":"NOT_VERIFIED","reason":"NO_ACTIVE_GITHUB_LEASE"}
    original_generation=found["generation"]
    # A single atomic contender attempt; never retry an uncertain mutation.
    result=service.claim(claim_key=k,owner="streamlit_lab_proof_20261119",
                         now_epoch=now_epoch,lease_seconds=600)
    if result["state"]!="ACTIVE_LEASE" or result["must_fetch"] is not False:
        return {"status":"NOT_VERIFIED","reason":"LEASE_CHANGED_OR_ACQUIRED"}
    persisted=service.observe(k)
    if (not persisted or persisted["state"]!="LEASED"
        or persisted["owner"]!=expected_owner
        or persisted["generation"]!=original_generation
        or persisted["expires_at"]<=now_epoch):
        return {"status":"NOT_VERIFIED","reason":"POST_CHECK_FAILED"}
    return {"status":"REMOTE_LEASE_RESPECTED","must_fetch":False,
            "owner_unchanged":True,"generation_unchanged":True}

def render():
    import streamlit as st
    import requests
    import time
    st.set_page_config(page_title="Kyoto isolated Turso cross-environment proof",page_icon="🧪")
    st.title("隔離Turso・Streamlit独立検証")
    st.warning("テスト専用。競馬の予想・購入や本番DBへの接続は一切行いません。")
    try:
        url=str(st.secrets["KYOTO_LAB_TURSO_DATABASE_URL"])
        token=str(st.secrets["KYOTO_LAB_TURSO_AUTH_TOKEN"])
        access=str(st.secrets["KYOTO_LAB_STREAMLIT_PROOF_PASSWORD"])
        if len(access)<16:raise ValueError("access_not_configured")
        service=lab_client(url,token,requests)
    except Exception:
        st.error("隔離テスト専用の接続設定が不足しています。")
        st.stop()
    provided=st.text_input("診断用パスワード",type="password")
    if not hmac.compare_digest(provided,access):
        st.info("診断用パスワードが必要です。")
        st.stop()
    run_id=st.text_input("GitHub ActionsのRun ID",max_chars=20)
    if st.button("GitHubランナーが確定した予約を照合（読み取りのみ）"):
        try:
            st.json(observe_finished_gh_run(service,run_id))
        except Exception:
            st.error("検証不能。接続情報や例外詳細は表示しません。")
    st.divider()
    st.caption("下記はGitHub側が保持する有効なリースがある場合だけ実行してください。")
    confirm=st.text_input("書込み試験の確認文字列")
    if st.button("有効なGitHubリースへの競合を確認"):
        if confirm!=CONFIRM:
            st.error("確認文字列が一致しません。")
        else:
            try:
                st.json(attempt_active_lease(service,run_id,int(time.time())))
            except Exception:
                st.error("競合試験未確認。自動再試行はしません。")
    st.caption("この画面の成功はGitHubとStreamlitの相互確認だけであり、同時実行や全障害復旧の認定ではありません。")

if __name__=="__main__":
    render()
