"""Mocked Turso HTTP pipeline contract: NO external network or credentials.

Two separate client objects share one SQLite-backed fake endpoint. Tests
idempotency, readback, failure ambiguity, collision, corrections, same frame,
wrong host and strict isolation. These tests do not prove real Turso access.
"""
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from diagnostics.kyoto_turso_isolated_virtual_store import (
    TursoLabStore,TursoLabRejected,TursoAmbiguous,EXPECTED_HOST,
)
from tests.test_kyoto_virtual_sqlite_journal import frozen,final

URL="libsql://"+EXPECTED_HOST
TOKEN="unit-test-fake-credential-not-real"

class FakeResponse:
    def __init__(self,status,body):
        self.status_code=status
        self.body=body
    def json(self):
        return self.body

class FakePipeline:
    """A mock HTTP service that uses local SQLite and raises no networking."""
    def __init__(self,db):
        self.db=str(db)
        self.fail_next=False
        self.fail_after_commit=False
        self.history=[]
        self.lock=threading.RLock()
    def post(self,url,headers,json,timeout,allow_redirects):
        assert url=="https://"+EXPECTED_HOST+"/v2/pipeline"
        assert headers["Content-Type"]=="application/json"
        assert headers["Authorization"]=="Bearer "+TOKEN
        assert timeout==12
        assert allow_redirects is False
        assert set(json)=={"requests"}
        with self.lock:
            self.history.append(json)
            if self.fail_next:
                self.fail_next=False
                raise TimeoutError("never print this secret or payload!")
            out=[]
            with sqlite3.connect(self.db) as conn:
                for req in json["requests"]:
                    if req["type"]=="close":
                        out.append({"type":"ok","response":{"type":"close"}})
                        continue
                    stmt=req["stmt"]
                    args=[a["value"] for a in stmt["args"]]
                    cursor=conn.execute(stmt["sql"],args)
                    if cursor.description:
                        rows=[[{"type":"text","value":str(x) if x is not None else None} for x in row]
                              for row in cursor.fetchall()]
                    else:
                        rows=[]
                    out.append({"type":"ok","response":{"type":"execute",
                        "result":{"rows":rows,
                                  "affected_row_count":max(cursor.rowcount,0)}}})
                conn.commit()
            if self.fail_after_commit:
                self.fail_after_commit=False
                raise TimeoutError("ambiguous after server commit")
            return FakeResponse(200,{"results":out})

class TursoIsolatedVirtualTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.transport=FakePipeline(Path(t.name)/"mock_server.sqlite")
        self.a=TursoLabStore(database_url=URL,token=TOKEN,transport=self.transport)
        self.b=TursoLabStore(database_url=URL,token=TOKEN,transport=self.transport)
        self.a.prepare_isolated_namespace()

    def test_cross_client_freeze_readback(self):
        p=frozen()
        a=self.a.append_freeze_lab(p)
        self.assertEqual(a["status"],"APPENDED")
        b=self.b.read_race_lab(p["race_id"])
        self.assertEqual(len(b["events"]),1)
        self.assertEqual(b["events"][0]["payload"],p)
        self.assertFalse(b["production_validated"])

    def test_duplicate_across_client_no_change(self):
        self.a.append_freeze_lab(frozen())
        r=self.b.append_freeze_lab(frozen())
        self.assertEqual(r["status"],"ALREADY_PRESENT")
        self.assertEqual(len(self.a.read_race_lab(frozen()["race_id"])["events"]),1)

    def test_conflicting_duplicate_rejected(self):
        self.a.append_freeze_lab(frozen())
        x=frozen();x["tickets"][0]["stake_yen"]=200
        with self.assertRaises(TursoLabRejected):self.b.append_freeze_lab(x)

    def test_versioned_result_after_remote_freeze(self):
        self.a.append_freeze_lab(frozen())
        self.b.append_final_lab(final(1,400))
        self.a.append_final_lab(final(2,700))
        values=self.b.read_race_lab(frozen()["race_id"])["events"]
        self.assertEqual(len(values),3)
        self.assertEqual([z["payload"]["result_version"] for z in values
                          if z["type"]=="FINAL"],[1,2])

    def test_repeated_correction_not_double_insert(self):
        self.a.append_freeze_lab(frozen())
        self.a.append_final_lab(final(1,400))
        x=self.b.append_final_lab(final(1,400))
        self.assertEqual(x["status"],"ALREADY_PRESENT")
        self.assertEqual(len(self.a.read_race_lab(frozen()["race_id"])["events"]),2)

    def test_missing_parent_final_rejected(self):
        with self.assertRaises(TursoLabRejected):self.a.append_final_lab(final())

    def test_final_version_gap_rejected(self):
        self.a.append_freeze_lab(frozen())
        with self.assertRaises(TursoLabRejected):self.a.append_final_lab(final(2,700))

    def test_rewrite_final_conflict(self):
        self.a.append_freeze_lab(frozen())
        self.a.append_final_lab(final(1,400))
        with self.assertRaises(TursoLabRejected):self.b.append_final_lab(final(1,700))

    def test_missing_secret_rejected(self):
        for v in ("", "short", "a secret with spaces",None):
            with self.subTest(v=v),self.assertRaises(TursoLabRejected):
                TursoLabStore(database_url=URL,token=v,transport=self.transport)

    def test_remote_wrong_database_rejected(self):
        for wrong in (
            "libsql://kyoto-keiba-ai-prod-papaneko-ai.aws-ap-northeast-1.turso.io",
            "https://"+EXPECTED_HOST+".evil.invalid/",
            "https://"+EXPECTED_HOST+":443/",
            "https://"+EXPECTED_HOST+"/v2/pipeline",
            "libsql://user:pass@"+EXPECTED_HOST,
            "http://"+EXPECTED_HOST,
            "libsql://"+EXPECTED_HOST+"?table=production",
            "file:///var/lib/paper.sqlite",
        ):
            with self.subTest(wrong=wrong),self.assertRaises(TursoLabRejected):
                TursoLabStore(database_url=wrong,token=TOKEN,transport=self.transport)

    def test_lost_ack_before_write_is_ambiguous_no_retry(self):
        self.transport.fail_next=True
        with self.assertRaisesRegex(TursoAmbiguous,"no_retry"):
            self.a.append_freeze_lab(frozen())
        self.assertEqual(self.b.read_race_lab(frozen()["race_id"])["events"],[])

    def test_lost_ack_after_commit_then_read_only_reconcile(self):
        # The caller is NOT allowed to blindly retry after a transport error.
        self.transport.fail_after_commit=True
        with self.assertRaisesRegex(TursoAmbiguous,"no_retry"):
            self.a.append_freeze_lab(frozen())
        self.assertEqual(len(self.b.read_race_lab(frozen()["race_id"])["events"]),1)
        # A subsequent explicit reconciliation can decide whether replay is safe.
        self.assertEqual(self.b.append_freeze_lab(frozen())["status"],"ALREADY_PRESENT")

    def test_non_200_unconfirmed(self):
        self.transport.fail_next=True
        with self.assertRaises(TursoAmbiguous):self.a.append_freeze_lab(frozen())

    def test_invalid_lab_scope_cannot_upgrade_to_live(self):
        p=frozen();p["provenance_scope"]="LIVE_JRA_AUTHENTICATED"
        with self.assertRaises(ValueError):self.a.append_freeze_lab(p)

    def test_wrong_ticket_market_type_rejected(self):
        p=frozen();p["ticket_type"]="REAL"
        with self.assertRaises(ValueError):self.a.append_freeze_lab(p)

    def test_valid_same_frame_bracket_saved_in_test_store(self):
        p=frozen();p["ticket_type"]="BRACKET"
        p["tickets"][0]["pair"]=[1,1]
        p["tickets"][1]["pair"]=[2,3]
        self.a.append_freeze_lab(p)
        self.assertEqual(self.b.read_race_lab(p["race_id"])["events"][0]["payload"],p)

    def test_out_of_range_frame_rejected(self):
        p=frozen();p["ticket_type"]="BRACKET"
        p["tickets"][1]["pair"]=[2,9]
        with self.assertRaises(ValueError):self.a.append_freeze_lab(p)

    def test_pre_race_temporal_rejection(self):
        p=frozen();p["frozen_utc"]="2026-11-14T05:01:00Z"
        with self.assertRaises(ValueError):self.a.append_freeze_lab(p)

    def test_no_unrelated_table_touched(self):
        self.a.append_freeze_lab(frozen())
        with sqlite3.connect(self.transport.db) as conn:
            names={x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(names,{"__kyoto_ai_p6_lab_v1_events"})

    def test_parameterized_sql_not_embedded_payload(self):
        p=frozen();p["model_version"]="x'); DROP TABLE production; --"
        self.a.append_freeze_lab(p)
        self.assertEqual(self.b.read_race_lab(p["race_id"])["events"][0]["payload"],p)
        stmts=[x["stmt"] for q in self.transport.history for x in q["requests"]
               if x["type"]=="execute"]
        self.assertFalse(any("DROP TABLE production" in x["sql"] for x in stmts))
        self.assertTrue(any("DROP TABLE production" in str(x["args"]) for x in stmts))

if __name__=="__main__":unittest.main()
