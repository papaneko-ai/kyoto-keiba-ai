"""G04 replay only historical 2026-11-06 JRA profile HTML from archived evidence.

This does NOT fetch JRA or claim a future-day as-of snapshot. Both the
archived original SHA and its historical 148-runner registry must agree.
"""
from __future__ import annotations
import hashlib,io,json,re,tarfile,zipfile
from datetime import date,datetime,timezone
from pathlib import Path
from bs4 import BeautifulSoup
from diagnostics.jra_prior_form_offline import parse_horse_history
from diagnostics.jra_p1_sp_profile_offline import parse as parse_sp
from diagnostics.kyoto_g04_all_horse_profiles import _metadata

INDEX=Path("docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json")
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
def replay(archive_path):
    source=Path(archive_path)
    if not source.is_file() or source.stat().st_size>12_000_000:
        raise ValueError("missing_or_oversized_offline_archive")
    rows=json.loads(INDEX.read_text(encoding="utf8"))
    idx={(v["race_number"],v["horse_number"]):v for v in rows}
    if len(rows)!=148 or len(idx)!=148:
        raise ValueError("old_148_runner_source_registry_inconsistent")
    data=source.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as wrapper:
        if wrapper.namelist()!=["kyoto_ai_20261106_eod_complete_bundle.zip"]:
            raise ValueError("outer_artifact_member_mismatch")
        with zipfile.ZipFile(io.BytesIO(wrapper.read(wrapper.namelist()[0]))) as inner:
            archived=inner.read("source_originals.tar.gz")
    successful=[];sp_ok=[];diagnostic=0
    with tarfile.open(fileobj=io.BytesIO(archived),mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".html"):
                continue
            if member.size>1_500_000:
                raise ValueError("unsafe_original_size")
            filename=member.name.rsplit("/",1)[-1]
            match=re.fullmatch(r"race_(\d{2})_horse_(\d{2})(_diagnostic)?\.html",filename)
            sp=re.fullmatch(r"sp_(\d{2})r_horse(\d{2})\.html",filename)
            if match:race,number=map(int,match.groups()[:2])
            elif sp:race,number=map(int,sp.groups())
            else:raise ValueError("unrecognized_archived_profile_filename")
            row=idx.get((race,number))
            if row is None:raise ValueError("archived_profile_not_in_148_registry")
            raw=tar.extractfile(member).read()
            sha=hashlib.sha256(raw).hexdigest()
            if match:
                if sha!=row.get("profile_source_sha256"):
                    raise ValueError("historical_profile_SHA_mismatch")
                prior=parse_horse_history(raw,
                    source_url="https://jra.jp"+row["profile_href"],
                    fetched_at_utc=datetime(2026,11,6,tzinfo=timezone.utc),
                    prediction_cutoff_utc=CUTOFF,
                    target_date=date(2026,11,7),
                    expected_horse_name=row["horse_name"],
                    allow_verified_no_history=True)
                features=_metadata(raw,row["horse_name"])
                if prior["invalid_rows"] or not features["trainer"] or not features["sex"]:
                    raise ValueError("historical_profile_not_safely_parsed")
                successful.append((race,number,sha,len(prior["prior_rows"])))
                if match.group(3): diagnostic+=1
            else:
                parsed=parse_sp(raw,row["horse_name"])
                if parsed["invalid_rows"]:raise ValueError("historical_SP_profile_invalid")
                sp_ok.append((race,number,sha,len(parsed["prior_rows"])))
    if len(successful)!=84 or len(sp_ok)!=2 or diagnostic!=1:
        raise ValueError("historical_source_coverage_mismatch")
    return {"schema":"kyoto_g04_historical_archive_replay.v1",
            "actual_archived_pc_profiles_verified":84,
            "actual_archived_sp_profiles_verified":2,
            "PC_prior_finishes":sum(r[3] for r in successful),
            "diagnostic_profile_replayed":diagnostic,
            "registry_original_sha256s_all_match":True,
            "new_jra_http_requests":0,
            "current_jockey_verified":False,
            "official_permanent_horse_ids_verified":False,
            "2026_11_21_22_capture_success_claimed":False,
            "prediction_ready":False}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--archive",required=True)
    args=p.parse_args()
    print(json.dumps(replay(args.archive),ensure_ascii=False,sort_keys=True))
