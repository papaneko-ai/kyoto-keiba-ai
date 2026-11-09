"""Historical official source snapshots only; no network or fabricated odds."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from diagnostics.p1_historical_day_handoff import evaluate, DayHandoffRejected

SOURCE=Path(__file__).resolve().parents[1]/"docs"/"diagnostics"

class ArchivedDayHandoffTests(unittest.TestCase):
    def setup_modified(self,path,fn):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        shutil.copytree(SOURCE,root/"archive")
        doc=root/"archive"/path
        obj=json.loads(doc.read_text(encoding="utf-8"))
        fn(obj)
        doc.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")
        return root/"archive"

    def test_historical_12_races_148_horses_396_dates(self):
        result=evaluate(SOURCE)
        self.assertEqual((result["race_count"],result["runner_count"],result["historical_prior_dates"]),(12,148,396))
        self.assertEqual(result["actual_20261107_prerace_quinella_prices"],0)
        self.assertEqual(result["actual_20261107_prerace_bracket_prices"],0)
        self.assertEqual(result["virtual_tickets"],[])

    def test_all_race_snapshots_present(self):
        result=evaluate(SOURCE)
        self.assertEqual(len(result["sources_checked"]),12)
        self.assertEqual(sum(r["runners"] for r in result["race_statuses"]),148)

    def test_past_final_not_prerace(self):
        result=evaluate(SOURCE)
        self.assertEqual(result["existing_official_market_parse_20261031"]["quinella_pairs"],120)
        self.assertEqual(result["existing_official_market_parse_20261031"]["bracket_pairs"],36)
        self.assertFalse(result["real_prediction_ready"])

    def test_deterministic(self):
        self.assertEqual(evaluate(SOURCE),evaluate(SOURCE))

    def test_bad_race_name_rejected(self):
        root=self.setup_modified("multirace_20261106/kyoto_01_snapshot.json",
                                 lambda d:d["runners"][0].update(horse_name="FAKE"))
        with self.assertRaisesRegex(DayHandoffRejected,"horse_identity_or_origin_disagreement"):
            evaluate(root)

    def test_source_sha_conflict_rejected(self):
        root=self.setup_modified("remaining8_20261106/kyoto_02_snapshot.json",
                                 lambda d:d.update(source_sha256="0"*64))
        with self.assertRaisesRegex(DayHandoffRejected,"horse_identity_or_origin_disagreement"):
            evaluate(root)

    def test_wrong_day_rejected(self):
        root=self.setup_modified("multirace_20261106/kyoto_12_snapshot.json",
                                 lambda d:d.update(race_date="2026-11-08"))
        with self.assertRaisesRegex(DayHandoffRejected,"racecard_identity_disagreement"):
            evaluate(root)

    def test_future_history_rejected(self):
        root=self.setup_modified("multirace_20261106/kyoto_01_snapshot.json",
                                 lambda d:d["runners"][0]["past_race_dates"].append("2026-11-07"))
        with self.assertRaisesRegex(DayHandoffRejected,"future_race_date"):
            evaluate(root)

    def test_faked_prerace_market_rejected(self):
        root=self.setup_modified("JRA_ODDS_READINESS_ACCEPTANCE_20261106.json",
                                 lambda d:d.update(pre_race_odds_available=True))
        with self.assertRaisesRegex(DayHandoffRejected,"unpublished_odds_evidence_contradicted"):
            evaluate(root)

    def test_historical_final_promoted_rejected(self):
        root=self.setup_modified("JRA_HISTORICAL_MATRIX_EVIDENCE_20261106.json",
                                 lambda d:d["markets"]["quinella"].update(pre_race_quote_accepted=True))
        with self.assertRaisesRegex(DayHandoffRejected,"historical_final_quotes_not_quarantined"):
            evaluate(root)

    def test_old_odds_menu_sha_change_rejected(self):
        root=self.setup_modified("JRA_PC_SP_ODDS_MENU_20261106.json",
                                 lambda d:d["sources"][0].update(content_sha256="0"*64))
        with self.assertRaisesRegex(DayHandoffRejected,"odds_menu_source_mismatch"):
            evaluate(root)

    def test_wrong_runner_count_rejected(self):
        root=self.setup_modified("JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json",
                                 lambda d:d["counts_by_race"].update({"2":14}))
        with self.assertRaisesRegex(DayHandoffRejected,"racecard_identity_disagreement"):
            evaluate(root)

if __name__=="__main__":
    unittest.main()
