import copy,json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_g05_official_track import capture_kyoto_track
from diagnostics.kyoto_impl30_day_coverage import extract_slot,combine,proof
from tests.test_kyoto_g05_official_track import html
DAY='20261128'; STAMP='2026-11-28T01:01:00Z'

class TrackUnion(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        capture_kyoto_track(self.root,DAY,lambda _:html(DAY),lambda:STAMP,allowed=True)
    def roster(self):
        return {'day':DAY,'run_id':'1','races':{'1':{'roster_digest':'r','named_roster_digest':'n','start_utc':'2026-11-28T02:00:00Z','racecard':proof('a'*64,'2026-11-28T00:00:00Z','r'),'horses':{'1':{}},'track':{},'markets':{}}}}
    def test_independent_track_only_fills_missing_before_start(self):
        slot=extract_slot(self.root,DAY,2);self.assertEqual(slot['races'],{})
        self.assertFalse(combine(DAY,[slot])['horse_denominator_complete'])
        r=combine(DAY,[self.roster(),slot]);w=r['races']['1']['track']['weather']
        self.assertEqual(w['state'],'SOURCE_VERIFIED');self.assertEqual(w['run_id'],'2')
        self.assertFalse(w['publication_time_independently_verified']);self.assertEqual(r['totals']['weather'],1)
        self.assertFalse(r['prediction_ready']);self.assertFalse(r['full_data_acquisition_certified'])
    def test_tamper_and_forged_receipt_rejected(self):
        p=self.root/'g05_track_receipt.json';old=p.read_bytes();d=json.loads(old);d['weather']='雨';p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):extract_slot(self.root,DAY,2)
        p.write_bytes(old);q=self.root/'g05_official_kyoto_track.html';q.write_bytes(q.read_bytes()+b'bad')
        with self.assertRaises(ValueError):extract_slot(self.root,DAY,2)
    def test_late_track_or_existing_primary_not_overridden(self):
        slot=extract_slot(self.root,DAY,2);r=self.roster();r['races']['1']['start_utc']='2026-11-28T01:00:00Z'
        self.assertEqual(combine(DAY,[r,slot])['totals']['weather'],0)
        r=self.roster();r['races']['1']['track']['weather']=proof('b'*64,'2026-11-28T00:01:00Z','雨')
        self.assertEqual(combine(DAY,[r,slot])['races']['1']['track']['weather']['run_id'],'1')
if __name__=='__main__':unittest.main()
