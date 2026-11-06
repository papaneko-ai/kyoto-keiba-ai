"""Replay official JRA odds market links and both real market HTML sources offline.
A historical final market is quarantined and never used as an as-of prediction.
"""
import argparse,json
from pathlib import Path
from diagnostics.jra_official_market_navigation import find_market_links
from diagnostics.jra_odds_matrix_parser import parse_matrix

def audit(menu,quinella,bracket,*,date,race,runners):
    nav=find_market_links(menu,expected_race_day=date,expected_race_number=race)
    q=parse_matrix(quinella,"quinella",expected_runners=runners)
    b=parse_matrix(bracket,"bracket_quinella")
    phase_nav=nav["source_final_odds_detected"]
    phase_q=q["historical_final_detected"]
    phase_b=b["historical_final_detected"]
    if phase_q!=phase_b or phase_q!=phase_nav:
        raise ValueError("market_sources_have_different_phases")
    return {"schema_version":"jra_official_both_market_audit.v1",
      "race_date":date,"race_number":race,
      "state":"QUARANTINED_FINAL_ODDS" if phase_q else "MATRIX_PARSED_PHASE_UNVERIFIED",
      "menu_sha256":nav["source_sha256"],
      "markets":{
        "quinella":{"market_action_sha256":nav["markets"]["quinella"]["cname_sha256"],
            "original_sha256":q["source_sha256"],"original_bytes":q["source_bytes"],
            "pair_count":q["pair_count"],"dimension":q["matrix_dimension"]},
        "bracket_quinella":{"market_action_sha256":nav["markets"]["bracket_quinella"]["cname_sha256"],
            "original_sha256":b["source_sha256"],"original_bytes":b["source_bytes"],
            "pair_count":b["pair_count"],"dimension":b["matrix_dimension"]}},
      "market_parsing_verified":True,
      "historical_final_not_prerace":phase_q,
      "prediction_ready":False,"training_ready":False}
def main():
    p=argparse.ArgumentParser()
    for key in ("menu","quinella","bracket","date","out"):
        p.add_argument("--"+key,required=True)
    p.add_argument("--race",type=int,required=True)
    p.add_argument("--runners",type=int,required=True)
    a=p.parse_args()
    result=audit(Path(a.menu).read_bytes(),Path(a.quinella).read_bytes(),
      Path(a.bracket).read_bytes(),date=a.date,race=a.race,runners=a.runners)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
