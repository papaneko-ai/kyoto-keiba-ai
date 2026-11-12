"""No network. Guard incorrect/tampered historical originals and receipts."""
import io,zipfile,unittest
from diagnostics.jra_historical_two_day_result_import import import_two_days,HistoricalImportRejected
class HistoricalOutcomeImportSafety(unittest.TestCase):
 def test_empty_fails(self):
  with self.assertRaises(HistoricalImportRejected):import_two_days(b"")
 def test_oversize_fails(self):
  with self.assertRaises(HistoricalImportRejected):import_two_days(b"x"*3_000_001)
 def test_unknown_member_fails(self):
  f=io.BytesIO()
  with zipfile.ZipFile(f,"w") as z:
   z.writestr("summary.json","{}")
   z.writestr("unexpected.html","x")
  with self.assertRaises(HistoricalImportRejected):import_two_days(f.getvalue())
 def test_invalid_archive_fails(self):
  with self.assertRaises(zipfile.BadZipFile):import_two_days(b"bad")
if __name__=="__main__":unittest.main()
