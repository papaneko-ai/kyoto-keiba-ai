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
            found=re.search(r"(?<![0-9])(?:0?([1-9])|1([0-2]))\\s*(?:R|レース)(?![0-9])",label,re.IGNORECASE)
            if not found:continue
            race=int(found.group(1) or "1"+found.group(2))
            # Race number AND entire day must be present in original observed token.
            if f"{race:02d}{DAY}" not in token:continue
            if race in results and results[race]["url"]!=url:
                raise OfflineRaceLinkRejected("ambiguous_observed_race_link")
            results[race]={"race_number":race,"url":url,"official_anchor_label":label}
        return {"schema":"kyoto_nov15_offline_race_links.v1","race_day":DAY,
            "state":"OFFLINE_OBSERVED_LINKS_ONLY",
            "source_observation_validation":verification["state"],
            "selection_sha256":hashlib.sha256(selection).hexdigest(),
            "meeting_sha256":hashlib.sha256(meeting).hexdigest(),
            "observed_meeting_url":observed_meeting,
            "race_links":[results[n] for n in sorted(results)],
            "racecard_originals_fetched":False,"roster_verified":False,
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
