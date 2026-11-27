import unittest,copy,tempfile
from pathlib import Path
from diagnostics.kyoto_impl36_cushion_day import combine,collect,NAME,WORKFLOW
D="20261128";REPO="papaneko-ai/kyoto-keiba-ai"
def coverage():
    return {"day":D,"race_denominator":12,"races":{str(i):{"state":"ROSTER_VERIFIED","start_utc":"2026-11-28T02:00:00Z"} for i in range(1,13)}}
def obs(stamp="2026-11-28T01:00:00Z",value="9.5"):
    return {"day":D,"captured_at_utc":stamp,"measurement_utc":"2026-11-27T22:00:00Z","cushion_value":value}
class Sidecar(unittest.TestCase):
    def test_before_start(self):
        c=coverage();old=copy.deepcopy(c);r=combine(D,c,[(1,obs())])
        self.assertEqual(r["prestart_verified_races"],12);self.assertEqual(c,old);self.assertFalse(r["prediction_ready"])
    def test_equal_and_after_excluded(self):
        for t in ("2026-11-28T02:00:00Z","2026-11-28T02:01:00Z"):
            self.assertEqual(combine(D,coverage(),[(1,obs(t))])["prestart_verified_races"],0)
    def test_conflict(self):
        r=combine(D,coverage(),[(1,obs()),(2,obs(value="9.6"))])
        self.assertEqual(r["races"]["1"]["state"],"SAME_TIMESTAMP_CONFLICT")
    def test_latest_valid(self):
        r=combine(D,coverage(),[(1,obs()),(2,obs("2026-11-28T01:30:00Z","9.6")),(3,obs("2026-11-28T02:30:00Z","9.9"))])
        self.assertEqual(r["races"]["1"]["run_id"],"2")
    def test_unknown_roster(self):
        c=coverage();c["races"]["1"]["state"]="NO_VERIFIED_ROSTER"
        self.assertEqual(combine(D,c,[(1,obs())])["prestart_verified_races"],11)
    def test_wrong_day(self):
        c=coverage();c["day"]="20261129"
        with self.assertRaises(ValueError):combine(D,c,[])
    def test_incomplete_index(self):
        a,e,c=collect(D,REPO,"",lambda *x:{"total_count":1,"workflow_runs":[]},lambda *x:None)
        self.assertFalse(c);self.assertEqual(a,[]);self.assertTrue(e)
    def test_wrong_run_never_download(self):
        r={"id":1,"name":NAME,"path":WORKFLOW,"head_branch":"other"}
        a,e,c=collect(D,REPO,"",lambda *x:{"total_count":1,"workflow_runs":[r]},lambda *x:self.fail("download"))
        self.assertFalse(c);self.assertEqual(a,[]);self.assertTrue(e)
if __name__=="__main__":unittest.main()
