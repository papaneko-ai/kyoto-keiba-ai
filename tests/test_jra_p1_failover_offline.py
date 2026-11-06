import unittest
from datetime import datetime,timezone
from diagnostics.jra_p1_failover_offline import ChannelResult,choose
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
        with self.assertRaisesRegex(ValueError,"unproven_validation"):
            choose(item("PC",raw=False),cutoff=CUTOFF)
    def test_no_fallback(self):
        self.assertEqual(choose(item("SP",False),cutoff=CUTOFF),
                         (None,"PRIMARY_FAILED"))
if __name__=="__main__":unittest.main()
