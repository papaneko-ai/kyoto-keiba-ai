"""Frozen source receipts: offline only, no network requests."""
import hashlib,tempfile,unittest
from diagnostics.jra_odds_source_archive import freeze_once,validate_receipt,SnapshotArchiveError
RAW=b"<html>official odds non-final</html>"
START="2026-11-07T06:00:00Z"
def row(**updates):
    d={"channel":"PC","market":"quinella","source_phase":"LIVE_PRE_RACE",
    "source_sha256":hashlib.sha256(RAW).hexdigest(),"source_bytes":len(RAW),
    "official_race_identity_verified":True,
    "source_url":"https://jra.jp/JRADB/accessO.html",
    "captured_at_utc":"2026-11-07T01:00:00Z",
    "usage":"PAPER_TRADE","race_id":"2026-11-07_KYOTO_11R",
    "market_integrity_state":"VALIDATED_MARKET_SOURCE","market_pair_count":10}
    d.update(updates)
    return d
class ImmutableArchive(unittest.TestCase):
 def test_first_write_and_idempotent(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(freeze_once(d,row(),RAW,race_start_utc=START)["state"],"FROZEN")
   self.assertEqual(freeze_once(d,row(),RAW,race_start_utc=START)["state"],"ALREADY_FROZEN")
 def test_conflicting_receipt_refused(self):
  with tempfile.TemporaryDirectory() as d:
   freeze_once(d,row(),RAW,race_start_utc=START)
   with self.assertRaises(SnapshotArchiveError):
    freeze_once(d,row(market_pair_count=5),RAW,race_start_utc=START)
 def test_wrong_digest_refused(self):
  with self.assertRaises(SnapshotArchiveError):validate_receipt(row(source_sha256="0"*64),RAW,race_start_utc=START)
 def test_history_refused(self):
  with self.assertRaises(SnapshotArchiveError):validate_receipt(row(source_phase="HISTORICAL_FINAL"),RAW,race_start_utc=START)
 def test_mobile_host_requires_mobile_channel(self):
  with self.assertRaises(SnapshotArchiveError):validate_receipt(row(channel="SP"),RAW,race_start_utc=START)
 def test_pc_evil_host_rejected(self):
  with self.assertRaises(SnapshotArchiveError):validate_receipt(row(source_url="https://jra.jp.evil.test/JRADB/accessO.html"),RAW,race_start_utc=START)
 def test_late_papertrade_refused(self):
  with self.assertRaises(SnapshotArchiveError):validate_receipt(row(captured_at_utc="2026-11-07T05:55:00Z"),RAW,race_start_utc=START)
 def test_no_integrity_gate_refused(self):
  with self.assertRaises(SnapshotArchiveError):validate_receipt(row(market_integrity_state="CLAIMED"),RAW,race_start_utc=START)
 def test_unsigned_time_refused(self):
  with self.assertRaises(SnapshotArchiveError):validate_receipt(row(captured_at_utc="2026-11-07T01:00:00"),RAW,race_start_utc=START)
if __name__=="__main__":unittest.main()
