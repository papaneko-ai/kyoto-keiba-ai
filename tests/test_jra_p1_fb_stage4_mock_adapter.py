import json,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from diagnostics.jra_p1_fb_stage4_mock_adapter import Source,Response,run,CUTOFF
T=datetime(2026,11,6,6,40,tzinfo=timezone.utc)
PC=Source("PC","https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103876/AA",True)
SP=Source("SP","https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AA",True)
RAW=b"<html><body>synthetic horse profile</body></html>"
def good(b,name):
    return {"horse_name":name,"prior_rows":[{"date":"2026-09-12","finish_position":1}],"invalid_rows":[]}
def faulty(b,name):
    raise ValueError("synthetic_invalid_history_rows")
def transport(ch,url):return Response(RAW,200,"text/html",url)
class Stage4Injected(unittest.TestCase):
    def execute(self,primary=PC,backup=SP,pars=None,trans=transport,at=T,prior=()):
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup)
        root=Path(d.name)/"case"
        return run(folder=root,primary=primary,secondary=backup,
             horse_name="モンドプリューム",race=11,number=1,roster_sha="a"*64,
             now=at,transport=trans,parsers=pars or {"PC":faulty,"SP":good},prior_attempts=prior),root
    def test_pc_failure_sp_success_preserves_pc_bytes_and_incident(self):
        r,p=self.execute()
        self.assertEqual(r["status"],"FALLBACK_VALID_PRIMARY_INCIDENT_OPEN_MOCK_ONLY")
        self.assertEqual(r["selected"],"SP")
        self.assertEqual(len(r["attempts"]),2)
        self.assertEqual((p/"original_pc.html").read_bytes(),RAW)
        self.assertEqual((p/"original_sp.html").read_bytes(),RAW)
        self.assertEqual(r["incidents"][0]["channel"],"PC")
        self.assertTrue(r["incidents"][0]["open"])
        self.assertEqual(r["actual_network_requests"],0)
    def test_sp_failure_pc_success(self):
        r,_=self.execute(SP,PC,{"PC":good,"SP":faulty})
        self.assertEqual(r["selected"],"PC")
        self.assertEqual(r["incidents"][0]["channel"],"SP")
    def test_primary_success_skips_backup(self):
        count=[]
        def t(c,u):count.append(c);return transport(c,u)
        r,_=self.execute(pars={"PC":good,"SP":faulty},trans=t)
        self.assertEqual(count,["PC"])
        self.assertEqual(r["status"],"PRIMARY_VALID_MOCK_ONLY")
    def test_both_failed(self):
        r,_=self.execute(pars={"PC":faulty,"SP":faulty})
        self.assertEqual(r["status"],"BOTH_FAILED_QUARANTINED")
        self.assertEqual(len(r["incidents"]),2)
    def test_http_failure_no_original_has_receipt_and_fallback(self):
        def t(ch,url):
            if ch=="PC":raise OSError("mock_http_unavailable")
            return transport(ch,url)
        r,p=self.execute(trans=t)
        self.assertFalse((p/"original_pc.html").exists())
        self.assertTrue(r["attempts"][0]["receipt_saved"])
        self.assertEqual(r["selected"],"SP")
    def test_bad_redirect_blocks_primary(self):
        def t(ch,url):
            if ch=="PC":return Response(RAW,200,"text/html","https://example.com/spoof")
            return transport(ch,url)
        r,p=self.execute(trans=t)
        self.assertEqual(r["selected"],"SP")
        self.assertFalse((p/"original_pc.html").exists())
    def test_unproven_backup_url_prevents_backup(self):
        r,_=self.execute(backup=Source("SP",SP.url,False))
        self.assertEqual(r["status"],"FALLBACK_BLOCKED")
        self.assertEqual(len(r["attempts"]),1)
    def test_duplicate_url_rejected_before_transport(self):
        from diagnostics.jra_p1_fb_request_budget_policy import Attempt
        old=Attempt("PC",PC.url,T-timedelta(seconds=10),11,1,"PARSER_FAILED",True)
        with self.assertRaisesRegex(ValueError,"already_requested_url"):
            self.execute(prior=(old,))
    def test_cutoff_refuses_every_request(self):
        with self.assertRaisesRegex(ValueError,"prediction_cutoff_passed"):
            self.execute(at=CUTOFF)
    def test_parser_identity_failure_quarantined(self):
        def wrong(b,n):return {"horse_name":"別馬","prior_rows":[],"invalid_rows":[]}
        r,_=self.execute(pars={"PC":wrong,"SP":wrong})
        self.assertEqual(r["status"],"BOTH_FAILED_QUARANTINED")
    def test_future_prior_race_rejected(self):
        def future(b,n):return {"horse_name":n,"prior_rows":[{"date":"2026-11-07"}],"invalid_rows":[]}
        r,_=self.execute(pars={"PC":future,"SP":future})
        self.assertEqual(r["status"],"BOTH_FAILED_QUARANTINED")
    def test_duplicate_incident_directory_cannot_replay(self):
        r,p=self.execute()
        with self.assertRaisesRegex(ValueError,"immutable_incident_directory_already_exists"):
            run(folder=p,primary=PC,secondary=SP,horse_name="モンドプリューム",
                race=11,number=1,roster_sha="a"*64,now=T,
                transport=transport,parsers={"PC":faulty,"SP":good})
    def test_provenance_missing_blocks(self):
        with self.assertRaisesRegex(ValueError,"unverified_primary_identity_or_url"):
            self.execute(primary=Source("PC",PC.url,True),at=T,pars={"PC":faulty},prior=()) if False else run(
                folder=tempfile.mkdtemp()+"/case",primary=PC,secondary=SP,
                horse_name="モンドプリューム",race=11,number=1,
                roster_sha="not_hex",now=T,transport=transport,parsers={"PC":good})
    def test_unpersistable_html_blocks_backup(self):
        from unittest.mock import patch
        with patch("pathlib.Path.write_bytes",side_effect=OSError("synthetic_source_write_failed")):
            r,p=self.execute()
        self.assertEqual(r["status"],"FALLBACK_BLOCKED")
        self.assertEqual(len(r["attempts"]),1)
        self.assertEqual(r["attempts"][0]["status"],"QUARANTINED")
        self.assertFalse(r["attempts"][0]["original_saved"])
        self.assertEqual(r["fallback_policy"]["reason"],"primary_failure_not_preserved")
    def test_prior_accepted_horse_with_different_url_blocks_before_transport(self):
        from diagnostics.jra_p1_fb_request_budget_policy import Attempt
        old=Attempt("SP","https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AB",
                    T-timedelta(minutes=2),11,1,"VALIDATED",True)
        with self.assertRaisesRegex(ValueError,"horse_profile_already_verified"):
            self.execute(prior=(old,))
    def test_no_unproved_primary_roster_source(self):
        with self.assertRaisesRegex(ValueError,"primary_roster_url_not_observed"):
            self.execute(primary=Source("PC",PC.url,False))
    def test_rejected_html_content_type_cannot_enter_parser(self):
        def typed(ch,url):
            if ch=="PC":return Response(RAW,200,"text/plain",url)
            return transport(ch,url)
        r,p=self.execute(trans=typed)
        self.assertEqual(r["selected"],"SP")
        self.assertFalse((p/"original_pc.html").exists())
if __name__=="__main__":unittest.main()
