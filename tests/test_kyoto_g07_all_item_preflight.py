import unittest
from diagnostics.kyoto_g07_all_item_preflight import audit,build_matrix,failover_proof
from diagnostics.kyoto_hybrid_multi_source import FIELDS
class G07Preflight(unittest.TestCase):
    def test_all_12r_148_identity(self):
        rows=build_matrix()
        self.assertEqual(len(rows),148)
        self.assertEqual(len(set((r["race"],r["horse_number"]) for r in rows)),148)
        self.assertEqual(set(r["race"] for r in rows),set(range(1,13)))
    def test_all_fields_explicitly_missing_without_fabrication(self):
        rows=build_matrix()
        self.assertTrue(all(set(r["fields"])==set(FIELDS) for r in rows))
        self.assertTrue(all(x["value"] is None and x["state"]=="MISSING"
                   for r in rows for x in r["fields"].values()))
    def test_two_way_failover(self):self.assertTrue(failover_proof()["pc_fault_sp_selected"])
    def test_conflict_quarantined(self):self.assertTrue(failover_proof()["conflicting_sources_quarantined"])
    def test_no_real_completeness_claim(self):
        r=audit()
        self.assertFalse(r["production_ready"])
        self.assertFalse(r["all_real_originals_verified"])
        self.assertEqual(r["field_state_slots"],148*len(FIELDS))
if __name__=="__main__":unittest.main()
