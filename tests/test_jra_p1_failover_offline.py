import unittest
import tempfile,json
from pathlib import Path
from datetime import datetime,timezone
from diagnostics.jra_p1_failover_offline import ChannelResult,choose,write_case
H="a"*64
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
def item(channel,verified=True,horse="試験馬",race=8,number=2,roster=H,
         value="b"*64,stamp="2026-11-06T06:00:00+00:00",raw=True):
    return ChannelResult(channel=channel,verified=verified,source_sha256=H,
        horse=horse,asof_utc=stamp,error="" if verified else "synthetic_parser_failure",
        race=race,number=number,roster_sha=roster,normalized_sha256=value,
        url_verified=True,raw_saved=raw)
class DualSourceOffline(unittest.TestCase):
    def test_pc_failure_sp_success(self):
        self.assertEqual(choose(item("PC",False),item("SP"),cutoff=CUTOFF),
                         ("SP","FALLBACK_VALID_PRIMARY_STILL_BROKEN"))
    def test_sp_failure_pc_success(self):
        self.assertEqual(choose(item("SP",False),item("PC"),cutoff=CUTOFF),
                         ("PC","FALLBACK_VALID_PRIMARY_STILL_BROKEN"))
    def test_pc_success_skips_backup(self):
        self.assertEqual(choose(item("PC"),item("SP"),cutoff=CUTOFF),
                         ("PC","PRIMARY_VALID"))
    def test_both_fail(self):
        self.assertEqual(choose(item("PC",False),item("SP",False),cutoff=CUTOFF),
                         (None,"BOTH_FAILED"))
    def test_conflict_blocks_auto_adoption(self):
        self.assertEqual(choose(item("PC"),item("SP",value="c"*64),
                         cutoff=CUTOFF,compare=True),(None,"SOURCE_CONFLICT"))
    def test_matching_sources(self):
        self.assertEqual(choose(item("PC"),item("SP"),cutoff=CUTOFF,compare=True),
                         ("PC","PRIMARY_VALID"))
    def test_cross_horse_rejected(self):
        with self.assertRaisesRegex(ValueError,"horse_identity_conflict"):
            choose(item("PC"),item("SP",horse="別の馬"),cutoff=CUTOFF)
    def test_roster_conflict_rejected(self):
        with self.assertRaisesRegex(ValueError,"horse_identity_conflict"):
            choose(item("PC"),item("SP",roster="c"*64),cutoff=CUTOFF)
    def test_same_channel_rejected(self):
        with self.assertRaisesRegex(ValueError,"not_cross_channel"):
            choose(item("PC"),item("PC"),cutoff=CUTOFF)
    def test_future_source_refused(self):
        with self.assertRaisesRegex(ValueError,"source_after_cutoff"):
            choose(item("PC",stamp="2026-11-07T00:00:00+00:00"),cutoff=CUTOFF)
    def test_no_source_provenance_refused(self):
        with self.assertRaisesRegex(ValueError,"original_not_preserved"):
            choose(item("PC",raw=False),cutoff=CUTOFF)
    def test_no_fallback(self):
        self.assertEqual(choose(item("SP",False),cutoff=CUTOFF),
                         (None,"PRIMARY_FAILED"))
    def test_failed_original_is_required(self):
        with self.assertRaisesRegex(ValueError,"original_not_preserved"):
            choose(item("PC",False,raw=False),cutoff=CUTOFF)
    def test_immutable_incident_recorder_keeps_failed_channel(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"case1"
            receipt=write_case(target,item("PC",False),item("SP"),cutoff=CUTOFF)
            self.assertEqual(receipt["selected_channel"],"SP")
            self.assertTrue(receipt["separate_incidents"][0]["incident_open"])
            self.assertFalse(receipt["separate_incidents"][1]["incident_open"])
            self.assertFalse(receipt["automatic_live_fallback"])
            self.assertEqual(json.loads((target/"receipt.json").read_text())["decision"],"FALLBACK_VALID_PRIMARY_STILL_BROKEN")
            with self.assertRaisesRegex(ValueError,"incident_receipt_already_exists"):
                write_case(target,item("PC",False),item("SP"),cutoff=CUTOFF)
    def test_incident_record_rejects_cross_horse_before_create(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"case2"
            with self.assertRaisesRegex(ValueError,"horse_identity_conflict"):
                write_case(target,item("SP",False),item("PC",horse="別馬"),cutoff=CUTOFF)
            self.assertFalse(target.exists())
class ComplementaryEvidenceTests(unittest.TestCase):
    def pack(self,channel,fields,**kwargs):
        from hashlib import sha256
        return {"channel_result":item(channel,**kwargs),"fields":fields,
                "fields_sha256":sha256(json.dumps(fields,sort_keys=True,
                  separators=(",",":"),ensure_ascii=False).encode()).hexdigest()}
    def reconcile(self,pc,sp,required=("horse_name","surface","distance_m")):
        from diagnostics.jra_p1_failover_offline import reconcile_complementary_fields
        return reconcile_complementary_fields(pc,sp,cutoff=CUTOFF,required_fields=required)
    def test_sp_only_field_is_retained(self):
        r=self.reconcile(self.pack("PC",{"horse_name":"試験馬","surface":"芝"}),
                         self.pack("SP",{"horse_name":"試験馬","distance_m":1600}))
        self.assertEqual(r["state"],"COMPLETE")
        self.assertEqual(r["merged"]["distance_m"],1600)
        self.assertEqual(r["provenance"]["distance_m"][0]["channel"],"SP")
        self.assertFalse(r["prediction_ready"])
    def test_pc_only_field_is_retained(self):
        r=self.reconcile(self.pack("PC",{"horse_name":"試験馬","surface":"芝","distance_m":1600}),
                         self.pack("SP",{"horse_name":"試験馬"}))
        self.assertEqual(r["state"],"COMPLETE")
        self.assertEqual(r["provenance"]["distance_m"][0]["channel"],"PC")
    def test_identical_value_has_both_originals(self):
        r=self.reconcile(self.pack("PC",{"horse_name":"試験馬","surface":"芝","distance_m":1600}),
                         self.pack("SP",{"horse_name":"試験馬","surface":"芝","distance_m":1600}))
        self.assertEqual(len(r["provenance"]["surface"]),2)
    def test_conflict_quarantines_entire_result(self):
        r=self.reconcile(self.pack("PC",{"horse_name":"試験馬","surface":"芝"}),
                         self.pack("SP",{"horse_name":"試験馬","surface":"ダート"}))
        self.assertEqual(r["state"],"CONFLICT_QUARANTINED")
        self.assertEqual(r["merged"],{})
        self.assertIn("surface",r["conflicts"])
    def test_missing_required_is_incomplete(self):
        r=self.reconcile(self.pack("PC",{"horse_name":"試験馬"}),
                         self.pack("SP",{"horse_name":"試験馬"}))
        self.assertEqual(r["state"],"INCOMPLETE")
        self.assertEqual(r["missing_required"],["distance_m","surface"])
    def test_cannot_merge_odds_from_different_times(self):
        with self.assertRaisesRegex(ValueError,"volatile_or_postrace_fields"):
            self.reconcile(self.pack("PC",{"market_odds":"12.4"}),
                           self.pack("SP",{"market_odds":"12.3"}),required=())
    def test_cross_horse_sources_blocked(self):
        with self.assertRaisesRegex(ValueError,"pc_sp_horse_identity_conflict"):
            self.reconcile(self.pack("PC",{"horse_name":"試験馬"}),
                           self.pack("SP",{"horse_name":"試験馬"},horse="別馬"))
    def test_fields_sha_tamper_rejected(self):
        bad=self.pack("PC",{"horse_name":"試験馬"})
        bad["fields"]["horse_name"]="改変"
        with self.assertRaisesRegex(ValueError,"field_original_sha_mismatch"):
            self.reconcile(bad,self.pack("SP",{"horse_name":"試験馬"}))
    def test_missing_raw_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError,"original_not_preserved"):
            self.reconcile(self.pack("PC",{"horse_name":"試験馬"},raw=False),
                           self.pack("SP",{"horse_name":"試験馬"}))
    def test_source_after_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError,"source_after_cutoff"):
            self.reconcile(self.pack("PC",{"horse_name":"試験馬"},
                            stamp="2026-11-07T00:00:00Z"),
                           self.pack("SP",{"horse_name":"試験馬"}))

if __name__=="__main__":unittest.main()
