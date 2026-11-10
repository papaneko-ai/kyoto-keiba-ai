import copy
import unittest
from diagnostics.kyoto_research_to_live_bridge import crosswalk, BridgeRejected

def samples():
    graduation={"schema":"kyoto_research_graduation_result.v1","graduation_percent":50.0,
                "areas":[{"id":f"RG-{i:02d}","component_pass":True,"integration_pass":False} for i in range(1,7)]}
    ids=("LIVE_RACECARD","LIVE_MARKET","PRE_RACE_FEATURES","MODEL_VALIDATION","MARKET_EV","REAL_PAPER_TRADE","OFFICIAL_SETTLEMENT","MOBILE_END_TO_END")
    operational={"schema":"kyoto_operational_readiness.v1","verified_points":0,
                "gates":[{"id":i,"state":"NO_OPERATIONAL_RECEIPT"} for i in ids]}
    return graduation,operational

class BridgeTests(unittest.TestCase):
    def test_no_live_evidence_means_zero_connection(self):
        g,o=samples()
        result=crosswalk(g,o,code_file_exists=lambda path:True)
        self.assertEqual(result["source_graduation_percent"],50.0)
        self.assertEqual(result["research_to_live_verified_areas"],0)
        self.assertFalse(result["all_connected"])
        self.assertFalse(result["real_purchase_authorized"])
    def test_all_research_complete_is_not_live_evidence(self):
        g,o=samples()
        for row in g["areas"]:row["integration_pass"]=True
        g["graduation_percent"]=100.0
        result=crosswalk(g,o,code_file_exists=lambda path:True)
        self.assertEqual(result["research_to_live_verified_areas"],0)
    def test_live_flags_without_research_integration_not_connected(self):
        g,o=samples()
        for row in o["gates"]:row["state"]="VERIFIED_OPERATIONAL"
        result=crosswalk(g,o,code_file_exists=lambda path:True)
        self.assertEqual(result["research_to_live_verified_areas"],0)
    def test_proven_complete_gate_is_connected_not_purchase(self):
        g,o=samples()
        for row in g["areas"]:row["integration_pass"]=True
        for row in o["gates"]:row["state"]="VERIFIED_OPERATIONAL"
        result=crosswalk(g,o,code_file_exists=lambda path:True)
        self.assertEqual(result["research_to_live_verified_areas"],6)
        self.assertTrue(result["all_connected"])
        self.assertFalse(result["real_purchase_authorized"])
    def test_missing_source_code_blocks_connection(self):
        g,o=samples()
        for row in g["areas"]:row["integration_pass"]=True
        for row in o["gates"]:row["state"]="VERIFIED_OPERATIONAL"
        result=crosswalk(g,o,code_file_exists=lambda path:False)
        self.assertEqual(result["research_to_live_verified_areas"],0)
    def test_missing_operational_gate_rejected(self):
        g,o=samples();o["gates"].pop()
        with self.assertRaisesRegex(BridgeRejected,"required_operational_gate_missing"):
            crosswalk(g,o,code_file_exists=lambda path:True)
    def test_mismatched_research_gate_rejected(self):
        g,o=samples();g["areas"][0]["id"]="INJECTED"
        with self.assertRaisesRegex(BridgeRejected,"misaligned"):
            crosswalk(g,o,code_file_exists=lambda path:True)
    def test_duplicate_operational_gate_rejected(self):
        g,o=samples();o["gates"].append(copy.deepcopy(o["gates"][0]))
        with self.assertRaisesRegex(BridgeRejected,"duplicate"):
            crosswalk(g,o,code_file_exists=lambda path:True)
    def test_invalid_operational_report_rejected(self):
        g,o=samples();o["schema"]="research"
        with self.assertRaisesRegex(BridgeRejected,"independent_operational"):
            crosswalk(g,o,code_file_exists=lambda path:True)
if __name__=="__main__":unittest.main()
