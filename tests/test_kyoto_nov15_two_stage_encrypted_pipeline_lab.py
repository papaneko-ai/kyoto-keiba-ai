"""True stage-to-stage source handling on synthetic bytes; never requests JRA."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_nov15_two_original_observer import observe,accept_observation
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence,decrypt_evidence
from diagnostics.kyoto_nov14_nov15_second_day_handoff import validate_day15_handoff
from diagnostics.kyoto_nov15_full_capture_seal import (
    encrypt_capture_directory,decrypt_capture_directory)
from diagnostics.kyoto_nov15_capture_acceptance import assess_saved_capture
from test_kyoto_nov14_nov15_second_day_handoff import SEL,MEET,SPEC,ROSTER,START

KEY="b"*64;REPO="papaneko-ai/kyoto-keiba-ai"
class R:
 def __init__(self,url,data):
    self.status=200;self.headers={"Content-Type":"text/html; charset=Shift_JIS"}
    self.url=url;self.data=data
 def read(self,n):return self.data[:n]
 def geturl(self):return self.url
 def __enter__(self):return self
 def __exit__(self,*e):return False
class Client:
 def __init__(self):self.calls=[]
 def open(self,req,timeout):
    self.calls.append(req.full_url)
    return R(req.full_url,SEL if len(self.calls)==1 else MEET)
class PipelineLab(unittest.TestCase):
 def test_observe_encrypt_decrypt_source_chain_capture_and_seal(self):
    with tempfile.TemporaryDirectory() as d:
      base=Path(d);client=Client()
      root=base/"observed"
      source=observe(root,now_utc="2026-11-14T09:00:00Z",
                     opener=client,allowed=True)
      self.assertEqual(len(client.calls),2)
      self.assertEqual(source["state"],"NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD")
      encrypt_evidence(root,base/"obssealed",key_hex=KEY,repo=REPO,run_id="45321")
      self.assertFalse((base/"obssealed/official_selection.html").exists())
      decrypt_evidence(base/"obssealed",base/"obsdecoded",key_hex=KEY,repo=REPO,run_id="45321")
      self.assertEqual(accept_observation(base/"obsdecoded")["state"],
                       "TWO_ORIGINALS_MATCH_RECEIPT_ONLY")
      preflight=validate_day15_handoff(
          spec_data=SPEC,roster=ROSTER,
          official_selection_original=(base/"obsdecoded/official_selection.html").read_bytes(),
          official_meeting_original=(base/"obsdecoded/official_meeting.html").read_bytes(),
          verified_start_utc=START)
      self.assertFalse(preflight["real_prerace_quinella_authenticated"])
      captured=base/"capture"
      (captured/"captured").mkdir(parents=True)
      (captured/"nov15_preflight_receipt.json").write_text(json.dumps(preflight))
      raws={"racecard":b"<html>lab roster</html>",
            "quinella":b"<html>lab quinella</html>",
            "bracket_quinella":b"<html>lab bracket quinella</html>"}
      files={"racecard":"official_racecard.html",
             "quinella":"quinella_original.html",
             "bracket_quinella":"bracket_quinella_original.html"}
      receipts=[]
      for step,raw in raws.items():
          (captured/"captured"/files[step]).write_bytes(raw)
          receipts.append({"step":step,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)})
      doc={"race_id":SPEC["race_id"],"state":"SOURCE_FROZEN",
           "pre_race_prices_accepted":True,
           "market_receipt":{"classification":"VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED"},
           "request_receipts":receipts,"prediction_ready":False,"training_ready":False}
      (captured/"captured/receipt.json").write_text(json.dumps(doc))
      report=assess_saved_capture(captured/"captured",expected_race_id=SPEC["race_id"])
      self.assertFalse(report["independent_official_source_authenticated"])
      encrypt_capture_directory(captured,base/"capturesealed",key_hex=KEY,repo=REPO,run_id="99881")
      self.assertFalse((base/"capturesealed/captured").exists())
      decrypt_capture_directory(base/"capturesealed",base/"capturerestored",
                                key_hex=KEY,repo=REPO,run_id="99881")
      replay=assess_saved_capture(base/"capturerestored/captured",
                                  expected_race_id=SPEC["race_id"])
      self.assertEqual(report,replay)
      self.assertEqual(len(client.calls),2)
if __name__=="__main__":unittest.main()
