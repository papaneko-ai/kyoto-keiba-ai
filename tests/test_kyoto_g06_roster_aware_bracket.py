import unittest
from diagnostics.kyoto_g06_roster_aware_bracket import parse_bracket_with_roster
from diagnostics.jra_odds_matrix_parser import OddsMatrixError
from diagnostics.jra_pc_sp_benchmark import frozen
def market(runners,missing=None,invalid=None):
    counts={}
    for n,f in runners:counts[f]=counts.get(f,0)+1
    n=max(counts)
    rows=[]
    for i in range(1,n+1):
        tokens=[]
        for j in range(i,n+1):
            good=i!=j or counts[i]>=2
            v="4.1" if good else "---"
            if (i,j)==missing:v="---"
            if (i,j)==invalid:v="2.0"
            tokens.extend([str(j),v])
        rows.append('<table class="basic narrow-xy waku">'+" ".join(tokens)+'</table>')
    return ('<html><title>枠連オッズ</title><body>2026年11月21日 京都 1レース 発売中'+''.join(rows)+'</body></html>').encode("cp932")
def lineup(r):return tuple((x["horse_number"],x["frame_number"]) for x in frozen(r)["runners"])
class RosterAware(unittest.TestCase):
    def test_12_actual_20261107_roster_shapes(self):
        total=0
        for race in range(1,13):
            runners=lineup(race)
            got=parse_bracket_with_roster(market(runners),runners)
            frames={f for n,f in runners}
            eligible=len(frames)*(len(frames)-1)//2+sum(
                 sum(x[1]==f for x in runners)>=2 for f in frames)
            self.assertEqual(got["pair_count"],eligible)
            self.assertFalse(got["pre_race_quote_accepted"])
            total+=len(runners)
        self.assertEqual(total,148)
    def test_one_duplicate_frame_does_not_require_36_odds(self):
        runners=lineup(1)
        got=parse_bracket_with_roster(market(runners),runners)
        self.assertEqual(got["pair_count"],29)
    def test_missing_eligible_pair_rejected(self):
        runners=lineup(1)
        with self.assertRaises(OddsMatrixError):
            parse_bracket_with_roster(market(runners,missing=(1,2)),runners)
    def test_ineligible_self_pair_must_not_be_priced(self):
        runners=lineup(1)
        with self.assertRaises(OddsMatrixError):
            parse_bracket_with_roster(market(runners,invalid=(1,1)),runners)
    def test_full_16_entrees_36_brackets(self):
        runners=lineup(11)
        got=parse_bracket_with_roster(market(runners),runners)
        self.assertEqual(got["pair_count"],36)
    def test_existing_paired_market_chain_for_nine_runner_race(self):
        from diagnostics.jra_market_source_chain import audit_source_originals
        from tests.test_kyoto_g06_twelve_race_dual_market_gate import race
        participants=lineup(1)
        a=race(1)
        a["active_runners"]=participants
        rows=[]
        for i in range(1,len(participants)):
            cells=[str(i)]
            for j in range(i+1,len(participants)+1):
                cells.extend([str(j),"3.2"])
            rows.append('<table class="basic narrow-xy umaren">'+" ".join(cells)+'</table>')
        a["market_raw"]["quinella"]=(
            "<html><title>馬連オッズ</title><body>2026年11月21日 京都 1レース 発売中"+
            "".join(rows)+"</body></html>").encode("cp932")
        a["market_raw"]["bracket_quinella"]=market(participants)
        output=audit_source_originals(**a)
        self.assertEqual(output["classification"],"VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED")
        self.assertEqual(output["markets"]["quinella"]["pair_count"],36)
        self.assertEqual(output["markets"]["bracket_quinella"]["pair_count"],29)
        self.assertFalse(output["prediction_ready"])
    def test_immutable_original_hash_changes_on_byte_edit(self):
        runners=lineup(1)
        first=market(runners)
        other=first.replace(b"4.1",b"4.2",1)
        a=parse_bracket_with_roster(first,runners)
        b=parse_bracket_with_roster(other,runners)
        self.assertNotEqual(a["source_sha256"],b["source_sha256"])
if __name__=="__main__":unittest.main()
