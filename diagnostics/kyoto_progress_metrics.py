"""Fixed-scope Kyoto AI progress measurement; GitHub CI proof is mandatory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = "papaneko-ai/kyoto-keiba-ai"
BRANCH = "jra-html-diagnostic-20261105"
WEIGHTS = {"P1": 25, "P2": 10, "P3": 15, "P4": 10,
           "P5": 5, "P6": 15, "P7": 10, "P8": 10}
RUBRIC_PATH = "docs/diagnostics/kyoto_progress_rubric_v1.json"
EVIDENCE_PATH = "docs/diagnostics/kyoto_progress_evidence_v1.json"
INCIDENTS_PATH = "docs/diagnostics/kyoto_progress_regressions_v1.json"
ARTIFACT = "kyoto-ai-progress-report"


class ProgressError(ValueError):
    pass


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_rubric(data):
    if data.get("schema") != "kyoto_progress_fixed_scope.v1":
        raise ProgressError("wrong fixed rubric version")
    if data.get("weights") != WEIGHTS:
        raise ProgressError("original P1-P8 weights were altered")
    criteria = data.get("criteria", [])
    ids = [c.get("id") for c in criteria]
    expected = [f"P{i}-{j:02d}" for i in range(1, 9) for j in range(1, 5)]
    if ids != expected:
        raise ProgressError("original 32 criteria were altered")
    for phase, weight in WEIGHTS.items():
        rows = [c for c in criteria if c.get("phase") == phase]
        if len(rows) != 4 or sum(c["points"] for c in rows) != weight:
            raise ProgressError("phase points do not match original total: " + phase)
        if any(type(c["points"]) is not int or c["points"] <= 0
               or not c.get("title") or not c.get("acceptance") for c in rows):
            raise ProgressError("invalid point or acceptance condition")
    if sum(c["points"] for c in criteria) != 100:
        raise ProgressError("score denominator must remain exactly 100")
    return hashlib.sha256(canonical(data)).hexdigest()


def verify_claims(rubric, evidence):
    if evidence.get("schema") != "kyoto_progress_proof_claims.v1":
        raise ProgressError("unsupported proof format")
    if evidence.get("scope_id") != rubric["scope_id"]:
        raise ProgressError("proof scope does not match fixed original scope")
    valid = {c["id"] for c in rubric["criteria"]}
    claims = evidence.get("claims", [])
    ids = [c.get("id") for c in claims]
    if ids != sorted(set(ids)):
        raise ProgressError("duplicate or unsorted proof claim")
    if not set(ids) <= valid:
        raise ProgressError("unknown or extra feature cannot change original score")
    for c in claims:
        if (type(c.get("run_id")) is not int or type(c.get("job_id")) is not int
                or len(c.get("head_sha", "")) != 40 or not c.get("workflow_name")):
            raise ProgressError("incomplete run/job/SHA proof")
        sources = c.get("source_paths")
        if not isinstance(sources, list) or not sources:
            raise ProgressError("claim has no concrete code or input source")
        if any(not isinstance(s, str) or s.startswith("/") or ".." in Path(s).parts
               for s in sources):
            raise ProgressError("unsafe source proof path")
    return claims


def run(*cmd, cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if proc.returncode:
        raise ProgressError("command failed: " + " ".join(cmd[:5]) + " " + proc.stderr[-300:])
    return proc.stdout


def gh(url):
    return json.loads(run("gh", "api", url))


def live_verifier(root):
    runs = {}
    jobs = {}

    def verify(claim):
        rid, jid = claim["run_id"], claim["job_id"]
        if rid not in runs:
            record = gh(f"repos/{REPO}/actions/runs/{rid}")
            if (record.get("status") != "completed" or record.get("conclusion") != "success"
                    or record.get("head_sha") != claim["head_sha"]
                    or record.get("head_branch") != BRANCH
                    or record.get("name") != claim["workflow_name"]
                    or record.get("repository", {}).get("full_name") != REPO):
                raise ProgressError("claimed workflow evidence did not verify: " + str(rid))
            runs[rid] = record
        if jid not in jobs:
            record = gh(f"repos/{REPO}/actions/jobs/{jid}")
            if (record.get("id") != jid or record.get("run_id") != rid
                    or record.get("conclusion") != "success"
                    or record.get("status") != "completed"):
                raise ProgressError("claimed CI job did not verify: " + str(jid))
            jobs[jid] = record
        run("git", "merge-base", "--is-ancestor", claim["head_sha"], "HEAD", cwd=root)
        for rel in claim["source_paths"]:
            if not (root / rel).is_file():
                raise ProgressError("verified source no longer exists: " + rel)
        return True

    return verify


def measure(rubric, evidence, verifier, previous=None, incident_register=None):
    key = verify_rubric(rubric)
    claims = verify_claims(rubric, evidence)
    passed = []
    for claim in claims:
        if verifier(claim) is not True:
            raise ProgressError("proof failed for " + claim["id"])
        passed.append(claim["id"])
    score = sum(row["points"] for row in rubric["criteria"] if row["id"] in passed)
    if score > 100:
        raise ProgressError("total exceeded 100 points")
    phases = {}
    for phase, weight in WEIGHTS.items():
        covered = [c for c in rubric["criteria"]
                   if c["phase"] == phase and c["id"] in passed]
        phases[phase] = {"earned": sum(c["points"] for c in covered),
                         "total": weight, "passed": len(covered), "conditions": 4}
    result = {
        "schema": "kyoto_progress_result.v1",
        "scope_id": rubric["scope_id"], "rubric_sha256": key,
        "score_percent": score, "total_points": 100,
        "passed_ids": passed,
        "pending_conditions": [{"id": c["id"], "points": c["points"], "title": c["title"]}
                               for c in rubric["criteria"] if c["id"] not in passed],
        "phases": phases, "comparison": "FIRST_OBJECTIVE_BASELINE",
        "previous_score_percent": None, "delta_points": None,
        "former_45_percent_was_an_estimate": True,
        "proof_run_ids": sorted({c["run_id"] for c in claims}),
        "regressions": []
    }
    if previous is not None:
        if previous.get("schema") != result["schema"] or previous.get("scope_id") != result["scope_id"]:
            raise ProgressError("previous result has incompatible schema or scope")
        if previous.get("rubric_sha256") != key:
            raise ProgressError("original completion standard silently changed")
        old = set(previous.get("passed_ids", []))
        if not old <= {c["id"] for c in rubric["criteria"]}:
            raise ProgressError("prior result contains unknown completed criterion")
        old_score = sum(c["points"] for c in rubric["criteria"] if c["id"] in old)
        if old_score != previous.get("score_percent"):
            raise ProgressError("prior score and completed conditions disagree")
        dropped = old - set(passed)
        incidents = (incident_register or {}).get("incidents", [])
        for criterion_id in sorted(dropped):
            matches = [i for i in incidents if i.get("criterion_id") == criterion_id]
            if len(matches) != 1:
                raise ProgressError("unexplained score decrease: " + criterion_id)
            incident = matches[0]
            if (incident.get("reason") not in ("IMPLEMENTATION_REGRESSION", "PREVIOUS_ACCEPTANCE_ERROR")
                    or not all(incident.get(k) for k in
                               ("description", "evidence_url", "recovery_condition"))):
                raise ProgressError("decrease needs cause, evidence and restoration criterion")
            result["regressions"].append(incident)
        result["comparison"] = "LIKE_FOR_LIKE_FIXED_SCOPE"
        result["previous_score_percent"] = old_score
        result["delta_points"] = score - old_score
    return result


def previous_artifact(current_run):
    records = gh(f"repos/{REPO}/actions/artifacts?name={ARTIFACT}&per_page=50")
    items = sorted(records.get("artifacts", []),
                   key=lambda x: x.get("created_at", ""), reverse=True)
    for item in items:
        prior = (item.get("workflow_run") or {}).get("id")
        if item.get("expired") or item.get("name") != ARTIFACT or not prior:
            continue
        if str(prior) == str(current_run):
            continue
        dest = Path("/tmp/kyoto-previous-progress")
        dest.mkdir(parents=True, exist_ok=True)
        run("gh", "run", "download", str(prior), "-R", REPO,
            "-n", ARTIFACT, "-D", str(dest))
        report = dest / "kyoto-progress.json"
        if not report.is_file():
            raise ProgressError("prior artifact exists but progress report is absent")
        return load(report)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not os.environ.get("GH_TOKEN"):
        raise ProgressError("GitHub authenticated online proof required; GH_TOKEN missing")
    rubric = load(root / RUBRIC_PATH)
    evidence = load(root / EVIDENCE_PATH)
    incidents = load(root / INCIDENTS_PATH)
    prior = previous_artifact(os.environ.get("GITHUB_RUN_ID", ""))
    result = measure(rubric, evidence, live_verifier(root), prior, incidents)
    result["source_commit"] = run("git", "rev-parse", "HEAD", cwd=root).strip()
    result["ci_run_id"] = os.environ.get("GITHUB_RUN_ID")
    result["repo"] = REPO
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canonical(result) + b"\n")
    print("KYOTO_PROGRESS_VERIFIED=" + str(result["score_percent"]) + "%")
    print("KYOTO_PROGRESS_DELTA=" + str(result["delta_points"]))
    print("KYOTO_PROGRESS_COMPARISON=" + result["comparison"])
    print("KYOTO_PROGRESS_REMAINING=" + str(len(result["pending_conditions"])))
    for phase, cell in result["phases"].items():
        print(phase + ": " + str(cell["earned"]) + "/" + str(cell["total"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ProgressError, OSError, json.JSONDecodeError) as exc:
        print("KYOTO_PROGRESS_FAIL_CLOSED: " + str(exc), file=sys.stderr)
        sys.exit(2)
