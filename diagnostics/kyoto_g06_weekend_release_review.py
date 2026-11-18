"""Byte-exact offline release review for Nov21/22 G06 candidate, no main mutation."""
from pathlib import Path
from hashlib import sha256
import json,re
OLD="c96df31542cb94435ca36cb4a1b8bd6de938233f"
NEW="a96a249250cb074c451e746228a6775169c025ed"
WORKFLOW=".github/workflows/kyoto-20261121-22-two-source-production-observer.yml"
CRONS=("15 0 21 11 *","15 1 21 11 *","5 2 21 11 *","50 2 21 11 *",
       "15 0 22 11 *","15 1 22 11 *","10 2 22 11 *","55 2 22 11 *")
def inspect(main,review,candidate):
    main,review,candidate=map(Path,(main,review,candidate))
    a=(main/WORKFLOW).read_bytes()
    b=(review/WORKFLOW).read_bytes()
    if a.count(OLD.encode())!=6 or b.count(NEW.encode())!=6:
        raise ValueError("six_source_pins_not_exact")
    if b!=a.replace(OLD.encode(),NEW.encode()):
        raise ValueError("unreviewed_workflow_difference")
    if b.replace(NEW.encode(),OLD.encode())!=a:
        raise ValueError("rollback_not_byte_identical")
    crons=re.findall(rb"^\s*- cron: '([^']+)'",a,re.M)
    if sorted(x.decode() for x in crons)!=sorted(CRONS):
        raise ValueError("scheduled_windows_mismatch")
    for token in (b"pc-originals-independent:",b"sp-originals-independent:",
                  b"KYOTO_JRA_ARCHIVE_AES256_HEX",b"cancel-in-progress: false"):
        if token not in a or token not in b:
            raise ValueError("source_protection_changed")
    for path in ("diagnostics/kyoto_g03_to_g06_input_adapter.py",
                 "diagnostics/kyoto_g06_all12_capture.py",
                 "diagnostics/kyoto_g06_nested_bundle.py",
                 "diagnostics/kyoto_nov15_encrypted_evidence.py",
                 "diagnostics/kyoto_weekend_capture.py",
                 "diagnostics/kyoto_g06_missing_market_retry.py"):
        if not (candidate/path).is_file():
            raise ValueError("candidate_function_missing:"+path)
    source=(candidate/"diagnostics/kyoto_weekend_capture.py").read_text(encoding="utf8")
    if "records_from_g03" not in source or "run_twelve" not in source or "bundle_g06" not in source:
        raise ValueError("candidate_g03_g06_crypto_not_connected")
    return {"schema":"kyoto_release_review_g06_20261121_22.v1",
        "main_sha256":sha256(a).hexdigest(),
        "review_sha256":sha256(b).hexdigest(),
        "rollback_sha256":sha256(b.replace(NEW.encode(),OLD.encode())).hexdigest(),
        "candidate_collector_sha":NEW,"old_collector_sha":OLD,
        "six_source_pin_changes_only":True,"eight_schedule_windows_untouched":True,
        "original_exact_rollback":True,
        "candidate_g03_g06_crypto_connected":True,
        "review_only_not_merged":True,"live_http_requests":0}
if __name__=="__main__":
    import sys
    result=inspect(*sys.argv[1:4])
    output=Path(sys.argv[4])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("G06_PRODUCTION_DIFF_ROLLBACK_VERIFIED")
