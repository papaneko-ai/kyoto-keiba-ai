"""G06 true 148-runner roster shapes across all 12 races with SYNTHETIC prices.

Tests data plumbing and eligibility, not live official price observations.
"""
import unittest,json
from pathlib import Path
from diagnostics.jra_pc_sp_benchmark import frozen
from diagnostics.kyoto_g06_twelve_race_dual_market_gate import audit_twelve_races
from diagnostics.kyoto_g06_roster_aware_bracket import parse_bracket_with_roster
from tests.test_kyoto_g06_twelve_race_dual_market_gate import fixture
from tests.test_kyoto_g06_roster_aware_bracket import market
def case(r):
    data=fixture(r)
    participants=tuple((x["horse_number"],x["frame_number"]) for x in frozen(r)["runners"])
    size=len(participants)
    rows=[]
    for i in range(1,size):
        row=[str(i)]
        for j in range(i+1,size+1):row += [str(j),"5.2"]
        rows.append('<table class="basic narrow-xy umaren">'+" ".join(row)+'</table>')
    data["market_raw"]["quinella"]=(
        f"<html><title>馬連オッズ</title><body>2026年11月21日 京都 {r}レース 発売中"+
        "".join(rows)+"</body></html>").encode("cp932")
    br=market(participants).decode("cp932").replace("京都 1レース",f"京都 {r}レース")
    data["market_raw"]["bracket_quinella"]=br.encode("cp932")
    data["active_runners"]=participants
    return data

def all_twelve():return {r:case(r) for r in range(1,13)}
class G06FullRoster(unittest.TestCase):
    def test_148_real_runners_12r_two_markets_complete_shape(self):
        cases=all_twelve()
        self.assertEqual(sum(len(x["active_runners"]) for x in cases.values()),148)
        result=audit_twelve_races(cases,provenance="SYNTHETIC_OFFLINE_TEST",expected_day="20261121")
        self.assertEqual(result["live_source_validated_count"],12)
        self.assertEqual(result["rejected_count"],0)
        for r in result["races"]:
            n=len(cases[r["race_number"]]["active_runners"])
            self.assertEqual(r["markets"]["quinella"]["pair_count"],n*(n-1)//2)
            self.assertEqual(r["markets"]["bracket_quinella"]["pair_count"],
              parse_bracket_with_roster(cases[r["race_number"]]["market_raw"]["bracket_quinella"],
               cases[r["race_number"]]["active_runners"])["pair_count"])
        self.assertFalse(result["evidence_independently_verified"])
        self.assertFalse(result["g06_certified"])
    def test_one_race_missing_quote_rejected_without_other_race_loss(self):
        cases=all_twelve()
        old=cases[7]["market_raw"]["quinella"]
        cases[7]["market_raw"]["quinella"]=old.replace(b"5.2",b"---",1)
        result=audit_twelve_races(cases,provenance="SYNTHETIC_OFFLINE_TEST",expected_day="20261121")
        self.assertEqual(result["rejected_count"],1)
        self.assertEqual(result["live_source_validated_count"],11)
        self.assertEqual(result["races"][6]["classification"],"REJECTED_OR_UNVERIFIED")
    def test_one_race_final_quote_rejected_as_live(self):
        cases=all_twelve()
        raw=cases[10]["market_raw"]["quinella"]
        cases[10]["market_raw"]["quinella"]=raw.replace("発売中".encode("cp932"),"最終オッズ".encode("cp932"),1)
        result=audit_twelve_races(cases,provenance="SYNTHETIC_OFFLINE_TEST",expected_day="20261121")
        self.assertEqual(result["live_source_validated_count"],11)
        self.assertEqual(result["rejected_count"],1)
    def test_earlier_genuine_historical_original_evidence_remains_separate(self):
        receipt=json.loads(Path("docs/diagnostics/JRA_HISTORICAL_MATRIX_EVIDENCE_20261106.json").read_text())
        self.assertEqual(receipt["source_classification"],"HISTORICAL_FINAL_NOT_PRERACE")
        self.assertEqual(receipt["markets"]["quinella"]["pair_count"],120)
        self.assertEqual(receipt["markets"]["bracket_quinella"]["pair_count"],36)
        self.assertFalse(receipt["markets"]["quinella"]["pre_race_quote_accepted"])
if __name__=="__main__":unittest.main()
