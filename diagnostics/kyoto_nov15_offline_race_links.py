"""Read-only derivation of observed Nov15 Kyoto race links from saved originals.

No network calls, synthetic race URLs, guessed start times, or roster claims.
Consumes two independently retained official HTML originals with matching
capture receipt before extracting links. The raw originals remain immutable.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path
from diagnostics.kyoto_nov15_two_original_observer import accept_observation
from diagnostics.jra_official_link_repair import observed_links,OFFICIAL_ENTRY

class OfflineRaceLinkRejected(ValueError):pass
DAY="20261115"

def derive_nov15_race_links(folder):
    root=Path(folder)
    if root.is_symlink() or not root.is_dir():
        raise OfflineRaceLinkRejected("original_directory_invalid")
    try:
        verification=accept_observation(root)
        receipt=json.loads((root/"receipt.json").read_text(encoding="utf8"))
        selection=(root/"official_selection.html").read_bytes()
        meeting=(root/"official_meeting.html").read_bytes()
        observed_meeting=receipt.get("observed_meeting_url")
        if not isinstance(observed_meeting,str):
            raise OfflineRaceLinkRejected("meeting_url_not_observed")
        meeting_links={url for url,label,token in observed_links(selection,OFFICIAL_ENTRY)
            if DAY in token and "京都" in label}
        if meeting_links!={observed_meeting}:
            raise OfflineRaceLinkRejected("meeting_not_linked_by_selection_original")
        results={}
        for url,label,token in observed_links(meeting,observed_meeting):
            if DAY not in token:continue
            if "京都" not in label and "京都" not in str(receipt.get("meeting_label","")):
                continue
            found=re.search(r"(?<![0-9])(?:0?([1-9])|1([0-2]))\s*(?:R|レース)(?![0-9])",label,re.IGNORECASE)
            if not found:continue
            race=int(found.group(1) or "1"+found.group(2))
            # Race number AND entire day must be present in original observed token.
            if f"{race:02d}{DAY}" not in token:continue
            if race in results and results[race]["url"]!=url:
                raise OfflineRaceLinkRejected("ambiguous_observed_race_link")
            results[race]={"race_number":race,"url":url,"official_anchor_label":label}
        # A saved third HTML original is source evidence, not a certified
        # numbered roster or a verified official start time.
        captured=receipt.get("racecard_original_fetched") is True
        observed_original=None
        if captured:
            number=receipt.get("racecard_number")
            url=receipt.get("observed_racecard_url")
            if (type(number) is not int or not 1<=number<=12
                or type(url) is not str
                or not any(r["race_number"]==number and r["url"]==url
                           for r in results.values())):
                raise OfflineRaceLinkRejected("saved_racecard_not_in_official_links")
            raw_race=(root/"official_racecard.html").read_bytes()
            # Reuse the already-tested Kyoto PC racecard parser; this is
            # offline structural diagnosis, NOT a source/cutoff certification.
            from diagnostics.jra_multi_capture_20261106 import parse as pc_parse
            try:
                parsed_rows,parse_errors=pc_parse(
                    raw_race,number,meeting_date="2026-11-15")
            except (ValueError,TypeError,UnicodeError) as exc:
                parsed_rows,parse_errors=[],["existing_pc_parser_rejected"]
            parser_result={
                "parser":"diagnostics.jra_multi_capture_20261106.parse",
                "parser_meeting_date":"2026-11-15",
                "parsed_runner_rows":len(parsed_rows),
                "errors":parse_errors,
                "structure_diagnostic_pass":bool(parsed_rows) and not parse_errors,
                "official_roster_authenticated":False,
                "independent_start_time_verified":False}
            # Carry an exact observed odds-navigation action forward rather
            # than stopping after HTML capture or inventing a market CNAME.
            # Reuse the established market capturer, offline (zero GET).
            from diagnostics.jra_one_shot_market_capture import exact_odds_action
            try:
                action=exact_odds_action(raw_race,"PC")
                odds_handoff={
                    "state":"ODDS_ACTION_OBSERVED_IN_SAVED_PC_RACECARD",
                    "channel":"PC",
                    "source_racecard_sha256":hashlib.sha256(raw_race).hexdigest(),
                    "source_racecard_url":url,
                    "source_captured_at_utc":receipt.get("racecard_captured_at_utc"),
                    "action_cname":action,
                    "official_menu_url":"https://jra.jp/JRADB/accessO.html",
                    "odds_original_fetched":False,
                    "market_values_verified":False,
                    "network_requests":0}
            except (ValueError,TypeError) as exc:
                odds_handoff={
                    "state":"OFFICIAL_ODDS_ACTION_MISSING_OR_AMBIGUOUS",
                    "channel":"PC",
                    "source_racecard_sha256":hashlib.sha256(raw_race).hexdigest(),
                    "failure_class":type(exc).__name__,
                    "odds_original_fetched":False,
                    "market_values_verified":False,
                    "network_requests":0}
            observed_original={
                "odds_navigation_handoff":odds_handoff,
                "race_number":number,"url":url,
                "sha256":hashlib.sha256(raw_race).hexdigest(),
                "bytes":len(raw_race),
                "captured_at_utc":receipt.get("racecard_captured_at_utc"),
                "existing_parser_diagnostic":parser_result,
                "state":"RAW_HTML_ONLY_NOT_ROSTER_OR_MARKET_VALIDATION"}
        return {"schema":"kyoto_nov15_offline_race_links.v1","race_day":DAY,
            "state":"OFFLINE_OBSERVED_LINKS_ONLY",
            "source_observation_validation":verification["state"],
            "selection_sha256":hashlib.sha256(selection).hexdigest(),
            "meeting_sha256":hashlib.sha256(meeting).hexdigest(),
            "observed_meeting_url":observed_meeting,
            "race_links":[results[n] for n in sorted(results)],
            "racecard_originals_fetched":captured,
            "saved_racecard_original":observed_original,
            # The unattended observer currently captures PC only. Treat it
            # as usable source evidence, NEVER as a completed PC/SP experiment.
            "hybrid_experiment":{
                "schema":"kyoto_nov15_hybrid_observer_status.v1",
                "PC":{"racecard_original_fetched":captured,
                      "structure_diagnostic_pass":bool(
                          observed_original and observed_original[
                              "existing_parser_diagnostic"]["structure_diagnostic_pass"])},
                "SP":{"racecard_original_fetched":False,
                      "independent_official_sp_racecard_url_verified":False},
                "dual_racecard_parity_verified":False,
                "dual_quinella_market_verified":False,
                "dual_bracket_market_verified":False,
                "full_hybrid_experiment_pass":False,
                "state":"INCOMPLETE_PC_ONLY_SP_MISSING"},
            "roster_verified":False,
            "start_times_verified":False,"quinella_market_verified":False,
            "bracket_market_verified":False,"http_requests":0}
    except OfflineRaceLinkRejected:raise
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise OfflineRaceLinkRejected("originals_or_receipt_inconsistent") from exc

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--originals",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args(argv)
    out=Path(a.output)
    if out.is_symlink() or out.exists() or not out.parent.is_dir():
        raise OfflineRaceLinkRejected("output_existing_or_invalid")
    report=derive_nov15_race_links(a.originals)
    with out.open("x",encoding="utf8") as dst:
        json.dump(report,dst,sort_keys=True,ensure_ascii=False,indent=2)
        dst.write("\n")
    print("NOV15_OFFLINE_OBSERVED_RACE_LINK_COUNT="+str(len(report["race_links"])))
    print("NOV15_OFFLINE_HTTP_REQUESTS=0")

if __name__=="__main__":main()
