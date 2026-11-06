import unittest
from diagnostics.jra_p1_fb_real_sources_adapter_gate import normalized,FIELDS
from diagnostics.jra_p1_failover_offline import ChannelResult,choose
from datetime import datetime,timezone
H="a"*64
CUT=datetime(2026,11,7,tzinfo=timezone.utc)
def item(ch,valid=True,hashval="b"*64):
    return ChannelResult(channel=ch,verified=valid,source_sha256=H,
        horse="同一馬",asof_utc="2026-11-06T06:00:00+00:00",
        race=11,number=1,roster_sha=H,normalized_sha256=hashval,
        url_verified=True,raw_saved=True)
class P1FBAdapterSafety(unittest.TestCase):
    def test_popularity_string_number_canonicalized(self):
        r={"date":"2026-01-01","venue":"京都","surface":"ダ",
           "distance_m":1400,"field_size":10,"finish_position":2,"popularity":"3"}
        self.assertEqual(normalized([r],[])["finishes"][0]["popularity"],3)
    def test_nonfinish_exclusion_normalized(self):
        a={"date":"2026-09-12","status":"除"}
        b={"date":"2026-09-12","status":"除外"}
        self.assertEqual(normalized([], [a]),normalized([], [b]))
    def test_field_difference_is_detectable(self):
        one={k:"a" for k in FIELDS};one["popularity"]="3";two=dict(one);two["distance_m"]="1600"
        self.assertNotEqual(normalized([one],[]),normalized([two],[]))
    def test_real_two_source_control_pc_to_sp(self):
        self.assertEqual(choose(item("PC",False),item("SP"),cutoff=CUT)[0],"SP")
    def test_real_two_source_control_sp_to_pc(self):
        self.assertEqual(choose(item("SP",False),item("PC"),cutoff=CUT)[0],"PC")
    def test_conflicting_normalized_hash_refused(self):
        self.assertEqual(choose(item("PC"),item("SP",hashval="c"*64),cutoff=CUT,compare=True),
                         (None,"SOURCE_CONFLICT"))
    def test_already_verified_not_displaced(self):
        self.assertEqual(choose(item("SP"),item("PC"),cutoff=CUT)[0],"SP")
    def test_cross_horse_blocked(self):
        x=item("SP"); y=ChannelResult(**{**item("PC").__dict__,"horse":"別馬"})
        with self.assertRaisesRegex(ValueError,"horse_identity_conflict"):
            choose(x,y,cutoff=CUT)
    def test_no_saved_raw_blocked(self):
        x=ChannelResult(**{**item("PC").__dict__,"raw_saved":False})
        with self.assertRaisesRegex(ValueError,"original_not_preserved"):
            choose(x,cutoff=CUT)
if __name__=="__main__":unittest.main()
