"""Fail-closed reuse inventory gate. It is a CI check, not branch protection."""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

REQUIRED = {
    "PC_RACECARD", "SP_RACECARD", "PC_PROFILE", "ODDS_FINAL_HTML",
    "PC_SP_ODDS_MENU", "QUINELLA_BRACKET_RESEARCH", "P6_PAPER_LAB",
    "P1_PROFILE_96_ARCHIVE", "P2_REAL_FEATURE_MATRIX",
    "PC_SP_MEASURED_ROUTING", "PC_SP_SPECIAL_HISTORY",
    "P1_FB_SHARED_LEDGER", "P1_ORIGINAL_BACKUP_RECOVERY",
    "P1_MULTIDAY_OFFICIAL_RESULTS", "P1_MARKET_TEMPORAL_QUALITY",
    "P1_HORSE_ID_CROSSWALK", "P1_RACE_CONDITIONS",
    "P1_JOCKEY_TRAINER_STATS", "P1_TRACK_WEATHER",
    "P1_TRAINING_WORKOUTS", "P1_LIVE_MARKET_OBSERVATION",
    "P6_HISTORICAL_PAYOUT", "P7_EVO01_INFORMATION_VALUE",
    "P2_THREE_WAY_CHRONOLOGY", "P8_STORAGE_PROTECTION",
}
STATES = {"IMPLEMENTED_VERIFIED", "IMPLEMENTED_PARTIAL", "DESIGNED_NOT_IMPLEMENTED"}


class PreflightBlocked(ValueError):
    pass


def _locked_file(root, name):
    if not isinstance(name, str) or not name or name.startswith("/") or "\\" in name:
        raise PreflightBlocked("unsafe_path")
    relative = Path(name)
    if ".." in relative.parts:
        raise PreflightBlocked("unsafe_path")
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise PreflightBlocked("missing_evidence_file:" + name)
    if not path.resolve().is_relative_to(root.resolve()):
        raise PreflightBlocked("escaped_evidence_file")


def verify(root, inventory, *, intent=None):
    root = Path(root)
    if not isinstance(inventory, dict) or inventory.get("schema") != "kyoto_feature_reuse_inventory.v1":
        raise PreflightBlocked("inventory_schema_invalid")
    rows = inventory.get("features")
    if not isinstance(rows, list) or len(rows) < len(REQUIRED):
        raise PreflightBlocked("inventory_incomplete")
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            raise PreflightBlocked("feature_invalid")
        key = row.get("id")
        if not isinstance(key, str) or not re.fullmatch("[A-Z0-9_]+", key) or key in found:
            raise PreflightBlocked("feature_id_invalid_or_duplicate")
        state = row.get("status")
        if state not in STATES:
            raise PreflightBlocked("status_invalid:" + key)
        paths = row.get("code_paths")
        evidence = row.get("evidence_paths")
        if not isinstance(paths, list) or not isinstance(evidence, list) or not evidence:
            raise PreflightBlocked("feature_sources_missing:" + key)
        if state != "DESIGNED_NOT_IMPLEMENTED" and not paths:
            raise PreflightBlocked("existing_code_not_named:" + key)
        if state == "DESIGNED_NOT_IMPLEMENTED" and paths:
            raise PreflightBlocked("designed_status_has_existing_code:" + key)
        for path in paths + evidence:
            _locked_file(root, path)
        entry = row.get("canonical_entrypoint")
        if entry is not None:
            if (not isinstance(entry, dict) or set(entry) != {"path", "symbol"}
                    or entry.get("path") not in paths
                    or not isinstance(entry.get("symbol"), str)
                    or not re.fullmatch("[a-zA-Z_][a-zA-Z0-9_]*", entry["symbol"])):
                raise PreflightBlocked("canonical_entrypoint_invalid:" + key)
            original = root / entry["path"]
            try:
                parsed = ast.parse(original.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeError) as exc:
                raise PreflightBlocked("canonical_entrypoint_source_unreadable:" + key) from exc
            names = {node.name for node in parsed.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            if entry["symbol"] not in names:
                raise PreflightBlocked("canonical_entrypoint_missing:" + key)
        if not isinstance(row.get("remaining"), str) or not row["remaining"].strip():
            raise PreflightBlocked("missing_remaining_work:" + key)
        found[key] = row
    if not REQUIRED.issubset(found):
        raise PreflightBlocked("required_feature_missing:" + ",".join(sorted(REQUIRED - set(found))))
    if intent is not None:
        if not isinstance(intent, dict) or intent.get("schema") != "kyoto_change_intent.v1":
            raise PreflightBlocked("intent_schema_invalid")
        changes = intent.get("changes")
        if not isinstance(changes, list) or not changes:
            raise PreflightBlocked("intent_changes_missing")
        change_ids=set()
        for item in changes:
            if not isinstance(item, dict) or item.get("feature_id") not in found:
                raise PreflightBlocked("intent_feature_not_registered")
            if item["feature_id"] in change_ids:
                raise PreflightBlocked("duplicate_intent_feature:" + item["feature_id"])
            change_ids.add(item["feature_id"])
            action = item.get("action")
            if action not in ("REUSE", "REPAIR", "INTEGRATE", "NEW"):
                raise PreflightBlocked("intent_action_invalid")
            earlier = found[item["feature_id"]]
            if action == "NEW" and (earlier["code_paths"] or earlier["status"] != "DESIGNED_NOT_IMPLEMENTED"):
                raise PreflightBlocked("duplicate_new_implementation:" + item["feature_id"])
            if not isinstance(item.get("rationale"), str) or len(item["rationale"].strip()) < 12:
                raise PreflightBlocked("missing_reuse_rationale")
    return {"status": "PREFLIGHT_EVIDENCE_CHECK_PASS", "features_checked": len(found),
            "intent_checked": intent is not None, "claim_document_understanding": False,
            "branch_protection_confirmed": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--inventory", default="docs/diagnostics/kyoto_feature_reuse_inventory_v1.json")
    p.add_argument("--intent", default="docs/diagnostics/kyoto_change_intent_v1.json")
    args = p.parse_args()
    try:
        inventory = json.loads((args.root / args.inventory).read_text(encoding="utf-8"))
        intent = json.loads((args.root / args.intent).read_text(encoding="utf-8"))
        print(json.dumps(verify(args.root, inventory, intent=intent), sort_keys=True))
    except (PreflightBlocked, OSError, ValueError) as exc:
        sys.exit("BLOCKED: " + str(exc))


if __name__ == "__main__":
    main()
