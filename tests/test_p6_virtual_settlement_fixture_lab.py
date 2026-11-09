"""Only laboratory examples. No JRA results, no wagers or real scores."""
import copy
import unittest
from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture, settle_fixture, LabRejected

SHA="a"*64
BASE={"scenario_id":"LAB-CASE-01","ticket_type":"QUINELLA",
      "frozen_utc":"2026-11-13T04:00:00Z",
      "cutoff_utc":"2026-11-14T04:50:00Z",
      "model_version":"lab-pl-0-unvalidated","source_sha256":SHA,
      "tickets":[{"pair":[2,1],"stake_yen":200,"probability":.15,"odds":5.0},
                 {"pair":[1,3],"stake_yen":100,"probability":.10,"odds":8.0}]}

def event(version=1,state="PAYOUT_FINAL",**changes):
    e={"scenario_id":"LAB-CASE-01","source_kind":"FIXTURE",
       "version":version,"state":state,
       "payout_per_100":{"1-2":500},"refunded_pairs":[]}
    e.update(changes)
    return e

class VirtualLabTests(unittest.TestCase):
    def setUp(self):
        self.f=freeze_fixture(**copy.deepcopy(BASE))

    def test_frozen_canonical_pair_and_hash(self):
        self.assertEqual(self.f["frozen"]["tickets"][0]["pair"],[1,2])
        self.assertEqual(freeze_fixture(**copy.deepcopy(BASE)),self.f)

    def test_no_events_unsettled_not_loss(self):
        r=settle_fixture(self.f,[])
        self.assertEqual(r["status"],"UNSETTLED")
        self.assertIsNone(r["profit_yen"])

    def test_preliminary_does_not_count_money(self):
        r=settle_fixture(self.f,[event(state="RESULT_PRELIMINARY")])
        self.assertIsNone(r["payout_yen"])
        self.assertFalse(r["official_confirmation"])

    def test_final_100_yen_payout_math(self):
        r=settle_fixture(self.f,[event()])
        self.assertEqual(r["stake_yen"],300)
        self.assertEqual(r["payout_yen"],1000)
        self.assertEqual(r["profit_yen"],700)
        self.assertEqual(r["ticket_hits"],1)
        self.assertFalse(r["official_confirmation"])

    def test_retransmission_idempotent(self):
        x=event()
        self.assertEqual(settle_fixture(self.f,[x]),settle_fixture(self.f,[x,x]*10))

    def test_correction_replaces_not_adds(self):
        r=settle_fixture(self.f,[event(1),event(2,payout_per_100={"1-3":800})])
        self.assertEqual(r["payout_yen"],800)
        self.assertEqual(r["profit_yen"],500)
        self.assertEqual(r["event_version"],2)

    def test_refunds_return_stake(self):
        r=settle_fixture(self.f,[event(payout_per_100={},refunded_pairs=[[1,3]])])
        self.assertEqual(r["payout_yen"],100)
        self.assertEqual(r["refunded_stake_yen"],100)
        self.assertEqual(r["profit_yen"],-200)

    def test_conflicting_version_rejected(self):
        with self.assertRaisesRegex(LabRejected,"version_payload_conflict"):
            settle_fixture(self.f,[event(),event(payout_per_100={})])

    def test_tampered_prediction_refused(self):
        changed=copy.deepcopy(self.f)
        changed["frozen"]["tickets"][0]["stake_yen"]=5000
        with self.assertRaisesRegex(LabRejected,"freeze_tampered"):
            settle_fixture(changed,[event()])

    def test_post_cutoff_cannot_freeze(self):
        p=copy.deepcopy(BASE)
        p["frozen_utc"]=p["cutoff_utc"]
        with self.assertRaisesRegex(LabRejected,"freeze_after_cutoff"):
            freeze_fixture(**p)

    def test_nonfixture_event_rejected(self):
        with self.assertRaisesRegex(LabRejected,"nonfixture_event"):
            settle_fixture(self.f,[event(source_kind="OFFICIAL")])

    def test_live_scenario_marker_rejected(self):
        p=copy.deepcopy(BASE);p["scenario_id"]="KYOTO-LIVE"
        with self.assertRaisesRegex(LabRejected,"lab_marker_required"):
            freeze_fixture(**p)

    def test_no_100_yen_fractional_bet(self):
        p=copy.deepcopy(BASE);p["tickets"][0]["stake_yen"]=250
        with self.assertRaisesRegex(LabRejected,"stake_invalid"):
            freeze_fixture(**p)

    def test_bracket_same_frame_allowed(self):
        p=copy.deepcopy(BASE);p["scenario_id"]="LAB-FRAME"
        p["ticket_type"]="BRACKET";p["tickets"]=[{"pair":[1,1],"stake_yen":100,"probability":.05,"odds":10.0}]
        f=freeze_fixture(**p)
        e={"scenario_id":"LAB-FRAME","source_kind":"FIXTURE","version":1,
           "state":"PAYOUT_FINAL","payout_per_100":{"1-1":1000},"refunded_pairs":[]}
        self.assertEqual(settle_fixture(f,[e])["payout_yen"],1000)

    def test_same_horse_quinella_invalid(self):
        p=copy.deepcopy(BASE);p["tickets"][0]["pair"]=[1,1]
        with self.assertRaisesRegex(LabRejected,"same_horse_quinella"):
            freeze_fixture(**p)

if __name__=="__main__":
    unittest.main()
