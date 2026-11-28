"""Independent adversarial probes of source-first foreseeable-risk enumeration."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_reverse_fmea_gate import LEDGER,inspect,AuditCoverageRejected

ROOT=Path(__file__).resolve().parents[1]
class SourceFirstCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads((ROOT/LEDGER).read_text(encoding="utf8"))
    def test_twenty_reachable_modules_seventy_six_functions_not_declared_complete(self):
        r=inspect(ROOT,self.doc)
        self.assertEqual(r["critical_modules"],29)
        self.assertEqual(r["top_level_functions_discovered"],103)
        self.assertEqual(r["top_level_functions_unregistered"],0)
        self.assertEqual(r["top_level_functions_not_yet_independently_reviewed"],99)
        self.assertGreater(r["class_methods_discovered_but_not_yet_independently_reviewed"],0)
        self.assertEqual(r["additional_predictable_failure_families"],25)
        self.assertGreater(r["high_severity_unresolved"],0)
        self.assertIs(r["completeness_demonstrated"],False)
    def test_transitive_source_dependencies_are_enumerated_and_registered(self):
        from diagnostics.kyoto_reverse_fmea_gate import reachable_local_modules
        seed={item["source"] for item in self.doc["surfaces"]}
        seen=reachable_local_modules(ROOT,seed)
        self.assertTrue(seed.issubset(seen))
        result=inspect(ROOT,self.doc)
        # Expanded G06's transitive source families are explicitly unresolved,
        # never silently certified. A failing review must not be disguised as
        # a 'no missing dependencies' report.
        self.assertEqual(
            result["additional_reachable_modules_not_yet_reviewed"],
            len(seen-seed))
        self.assertGreater(result["additional_reachable_modules_not_yet_reviewed"],0)
        self.assertEqual(set(result["additional_reachable_module_paths"]),seen-seed)
        self.assertEqual(result["top_level_functions_not_yet_independently_reviewed"],99)
        self.assertIs(result["completeness_demonstrated"],False)

    def assert_current_or_reopened(self,source,prior):
        for key in ("impl37_emergency_source_reopen","impl37_public_form_reopen","impl37_cancelled_number_reopen","impl37_adaptive_repair_reopen","impl37_both_days_aux_reopen","impl37_archive_salvage_reopen","impl37_g05_cancellation_isolation_reopen","impl37_track_canonical_source_reopen","impl37_cross_day_canonical_reopen","impl38_g05_current_layout_reopen"):
            rows=[r for r in self.doc[key]["sources"] if r["source"]==source]
            self.assertLessEqual(len(rows),1)
            if rows:
                self.assertEqual(rows[0]["old_blob"],prior)
                self.assertNotEqual(rows[0]["new_blob"],prior)
                self.assertEqual(rows[0]["review_status"],"UNREVIEWED_INDEPENDENT_FMEA")
                self.assertEqual(rows[0]["closed_risks"],0)
                prior=rows[0]["new_blob"]
        self.assertEqual(self.doc["source_git_blob_sha1"][source],prior)

    def test_emergency_source_reopen_keeps_exact_hash_and_unresolved_risks(self):
        import subprocess
        rows=self.doc["impl37_emergency_source_reopen"]["sources"]
        self.assertEqual(len(rows),len({r["source"] for r in rows}))
        self.assertIn("diagnostics/kyoto_weekend_sp_discovery.py",{r["source"] for r in rows})
        self.assertIn("diagnostics/kyoto_weekend_capture.py",{r["source"] for r in rows})
        for r in rows:
            self.assert_current_or_reopened(r["source"],r["old_blob"])
            self.assertEqual(subprocess.check_output(["git","hash-object",r["source"]],cwd=ROOT,text=True).strip(),self.doc["source_git_blob_sha1"][r["source"]])
        self.assertTrue(all(not r["test_proven"] and not r["remediated"] for r in self.doc["risks"]))

    def test_impl30_changed_source_reviews_reopened(self):
        self.assertEqual(len(self.doc["impl30_source_reopen"]),11)
        for record in self.doc["impl30_source_reopen"]:
            self.assertNotEqual(record["old_blob"],record["new_blob"])
            successor=next((x for x in [*self.doc["impl31_source_reopen"]["sources"],self.doc["impl31_final_sp_reopen"],self.doc["impl31_sp_route_reopen"]] if x["source"]==record["source"]),None)
            if successor is not None:
                self.assertEqual(successor["old_blob"],record["new_blob"])
                final=next((x for x in self.doc["impl31_sp_stop_boundary_reopen"]["sources"] if x["source"]==record["source"]),None)
                if final is not None:
                    self.assertEqual(final["old_blob"],successor["new_blob"])
                    later=self.doc["impl31_gap_priority_reopen"]
                    if later["source"]==record["source"]:
                        self.assertEqual(later["old_blob"],final["new_blob"])
                        latest=self.doc["impl32_nested_salvage_reopen"]
                        self.assertEqual(latest["source"],record["source"])
                        self.assertEqual(latest["old_blob"],later["new_blob"])
                        self.assertEqual(latest["closed_risks"],0)
                        self.assertEqual(latest["review_status"],"UNREVIEWED_INDEPENDENT_FMEA")
                        newest=next(x for x in self.doc["impl32_no_source_certainty_reopen"]["sources"] if x["source"]==record["source"])
                        self.assertEqual(newest["old_blob"],latest["new_blob"])
                        self.assertEqual(newest["closed_risks"],0)
                        self.assert_current_or_reopened(record["source"],newest["new_blob"])
                    else:
                        latest=self.doc["impl32_sp_actual_variant_reopen"]
                        if latest["source"]==record["source"]:
                            self.assertEqual(latest["old_blob"],final["new_blob"])
                            self.assert_current_or_reopened(record["source"],latest["new_blob"])
                            self.assertEqual(latest["review_status"],"UNREVIEWED_INDEPENDENT_FMEA")
                            self.assertEqual(latest["closed_risks"],0)
                        else:
                            self.assert_current_or_reopened(record["source"],final["new_blob"])
                else:
                    self.assert_current_or_reopened(record["source"],successor["new_blob"])
            else:
                newest=next((z for z in self.doc["impl32_no_source_certainty_reopen"]["sources"] if z["source"]==record["source"]),None)
                if newest is not None:
                    self.assertEqual(newest["old_blob"],record["new_blob"])
                    self.assertEqual(newest["closed_risks"],0)
                    self.assert_current_or_reopened(record["source"],newest["new_blob"])
                else:
                    self.assert_current_or_reopened(record["source"],record["new_blob"])
            rows=[x for x in self.doc["surfaces"] if x["source"]==record["source"]]
            self.assertEqual({x["function"] for x in rows},set(record["reopened_functions"]))
            self.assertTrue(all(x["review_status"]=="UNREVIEWED_INDEPENDENT_FMEA" for x in rows))
        self.assertTrue(all(x["remediated"] is False and x["test_proven"] is False for x in self.doc["risks"]))

    def test_impl31_changed_sources_reopen_without_risk_closure(self):
        receipt=self.doc["impl31_source_reopen"]
        self.assertEqual(receipt["prior_ledger_blob"],"ab47a06010411221db769a78537f1ceeef68b3ce")
        sources=receipt["sources"]
        self.assertEqual({x["source"] for x in sources},{"diagnostics/kyoto_weekend_capture.py","diagnostics/kyoto_nov15_encrypted_evidence.py"})
        self.assertEqual(len(sources),2)
        for x in sources:
            source=x["source"]
            self.assertNotEqual(x["old_blob"],x["new_blob"])
            final=next((y for y in self.doc["impl31_sp_stop_boundary_reopen"]["sources"] if y["source"]==source),None)
            if final is not None:
                self.assertEqual(final["old_blob"],x["new_blob"])
                later=self.doc["impl31_gap_priority_reopen"]
                if later["source"]==source:
                    self.assertEqual(later["old_blob"],final["new_blob"])
                    latest=self.doc["impl32_nested_salvage_reopen"]
                    self.assertEqual(latest["source"],source)
                    self.assertEqual(latest["old_blob"],later["new_blob"])
                    self.assertEqual(latest["closed_risks"],0)
                    newest=next(z for z in self.doc["impl32_no_source_certainty_reopen"]["sources"] if z["source"]==source)
                    self.assertEqual(newest["old_blob"],latest["new_blob"])
                    self.assertEqual(newest["closed_risks"],0)
                    self.assert_current_or_reopened(source,newest["new_blob"])
                else:
                    self.assert_current_or_reopened(source,final["new_blob"])
            else:
                self.assert_current_or_reopened(source,x["new_blob"])
            self.assertEqual(x["review_status"],"UNREVIEWED_INDEPENDENT_FMEA")
            self.assertEqual(x["closed_risks"],0)
            surfaces=[s for s in self.doc["surfaces"] if s["source"]==source]
            self.assertEqual(set(x["reopened_functions"]),{s["function"] for s in surfaces})
            self.assertTrue(all(s["review_status"]=="UNREVIEWED_INDEPENDENT_FMEA" for s in surfaces))
            self.assertEqual(set(x["affected_risk_ids"]),{r["id"] for r in self.doc["risks"] if any(source.split("/")[-1]+":" in a for a in r["affected_surfaces"])})
        self.assertEqual(len(self.doc["risks"]),25)
        self.assertTrue(all(r["remediated"] is False and r["test_proven"] is False for r in self.doc["risks"]))

    def test_function_omission_rejected(self):
        d=copy.deepcopy(self.doc)
        d["surfaces"].pop()
        with self.assertRaisesRegex(AuditCoverageRejected,"source_module_inventory_incomplete|unreviewed_or_stale_functions"):
            inspect(ROOT,d,verify_git=False)
    def test_fake_function_rejected(self):
        d=copy.deepcopy(self.doc)
        d["surfaces"][0]["function"]="not_existing_method"
        with self.assertRaisesRegex(AuditCoverageRejected,"unreviewed_or_stale_functions"):
            inspect(ROOT,d,verify_git=False)
    def test_issue_deletion_rejected(self):
        d=copy.deepcopy(self.doc)
        d["risks"].pop()
        with self.assertRaisesRegex(AuditCoverageRejected,"known_predictable_risk_missing"):
            inspect(ROOT,d,verify_git=False)
    def test_risk_claimed_fixed_without_evidence_rejected(self):
        d=copy.deepcopy(self.doc)
        d["risks"][0]["remediated"]=True
        with self.assertRaisesRegex(AuditCoverageRejected,"silently_marked_fixed"):
            inspect(ROOT,d,verify_git=False)
    def test_risk_references_nonexistent_function_rejected(self):
        d=copy.deepcopy(self.doc)
        d["risks"][0]["affected_surfaces"][1]="kyoto_weekend_capture.py:missing_fn"
        with self.assertRaisesRegex(AuditCoverageRejected,"risk_references_nonexistent"):
            inspect(ROOT,d,verify_git=False)
    def test_source_bytes_modified_without_new_fmea_rejected(self):
        import subprocess
        from unittest.mock import patch
        with patch("diagnostics.kyoto_reverse_fmea_gate.subprocess.check_output",
                   return_value=b"unauthorized altered historical byte stream"):
            with self.assertRaisesRegex(AuditCoverageRejected,"source_changed_requires_new_fmea"):
                inspect(ROOT,self.doc,verify_git=True)
    def test_source_first_fmea_never_promotes_unverified_live_market(self):
        self.assertEqual(self.doc["adjudication"]["result"],"STRUCTURALLY_ENUMERATED_BUT_FMEA_REVIEW_INCOMPLETE")
        self.assertFalse(self.doc["adjudication"]["live_data_authoritative"])
        self.assertTrue(self.doc["adjudication"]["claims_of_no_foreseeable_bugs_prohibited"])

if __name__=="__main__":
    unittest.main()
