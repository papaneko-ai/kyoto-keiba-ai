"""Read-only SHA identification for Streamlit Cloud shadow deployments.

The running instance must expose a real Git checkout SHA. An absent git
checkout is UNKNOWN and can NEVER silently certify a release. This function
does no network, writes no files and accesses no credentials.
"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

def source_checkout_sha(repository_root=None):
    root=Path(repository_root) if repository_root is not None else Path(__file__).resolve().parents[1]
    try:
        result=subprocess.run(["git","rev-parse","--verify","HEAD"],
                cwd=root,capture_output=True,text=True,timeout=3,check=False)
    except (FileNotFoundError,TimeoutError,subprocess.TimeoutExpired,OSError):
        return "UNKNOWN_NOT_CERTIFIED"
    sha=result.stdout.strip().lower()
    return sha if result.returncode==0 and re.fullmatch(r"[0-9a-f]{40}",sha) else "UNKNOWN_NOT_CERTIFIED"
