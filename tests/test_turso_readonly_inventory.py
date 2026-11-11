"""Offline destructive tests for isolated Turso read-only inventory."""
import unittest
from unittest.mock import Mock,patch
from diagnostics.turso_readonly_inventory import (
    EXPECTED_URL,ALLOWED_SQL,validate_url,validate_token,read_only_sql,inventory)

class TursoReadOnlyInventoryTests(unittest.TestCase):
    def test_allow_exact_test_database(self):
        self.assertEqual(validate_url(EXPECTED_URL),
          "https://kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io/v2/pipeline")
    def test_reject_every_other_endpoint(self):
        for url in ("libsql://production.turso.io","https://evil.test",
                    EXPECTED_URL+"?auth=secret",EXPECTED_URL+"/other",
                    "https://user:password@kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io",
                    EXPECTED_URL+":8080"):
            with self.subTest(url=url),self.assertRaises(ValueError):
                validate_url(url)
    def test_reject_mutating_sql(self):
        for sql in ("SELECT * FROM secrets","DELETE FROM rows","PRAGMA writable_schema=ON",
                    "INSERT INTO t VALUES (1)","SELECT name FROM sqlite_master"):
            with self.subTest(sql=sql),self.assertRaises(ValueError):
                read_only_sql(sql)
    def test_token_missing_rejected(self):
        for token in ("","short","a"*18+"\n"):
            with self.subTest(token=repr(token)),self.assertRaises(ValueError):
                validate_token(token)
    @patch("diagnostics.turso_readonly_inventory.requests.post")
    def test_only_table_metadata_and_no_values_reported(self,post):
        resp=Mock(status_code=200)
        resp.json.return_value={"results":[{"type":"ok","response":{
            "result":{"rows":[[{"value":"sample_table"}],[{"value":"other_table"}]]}}},
            {"type":"ok"}]}
        post.return_value=resp
        report=inventory(database_url=EXPECTED_URL,auth_token="X"*32)
        self.assertEqual(report["table_count_visible"],2)
        self.assertNotIn("sample_table",str(report))
        self.assertNotIn("X"*32,str(report))
        self.assertFalse(report["full_database_backup_verified"])
        k=post.call_args.kwargs
        self.assertFalse(k["allow_redirects"])
        self.assertEqual(k["json"]["requests"][0]["stmt"]["sql"],ALLOWED_SQL[0])
    @patch("diagnostics.turso_readonly_inventory.requests.post")
    def test_http_error_fails_closed(self,post):
        post.return_value=Mock(status_code=401)
        with self.assertRaises(RuntimeError):
            inventory(database_url=EXPECTED_URL,auth_token="X"*32)
    @patch("diagnostics.turso_readonly_inventory.requests.post")
    def test_unsafe_table_name_fails_closed(self,post):
        resp=Mock(status_code=200)
        resp.json.return_value={"results":[{"type":"ok","response":{
            "result":{"rows":[[{"value":"table; DROP TABLE users"}]]}}},
            {"type":"ok"}]}
        post.return_value=resp
        with self.assertRaises(RuntimeError):
            inventory(database_url=EXPECTED_URL,auth_token="X"*32)

if __name__=="__main__":
    unittest.main()
