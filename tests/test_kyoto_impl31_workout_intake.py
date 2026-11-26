import copy, hashlib, json, unittest
from diagnostics.kyoto_impl31_workout_intake import inspect_workouts
RAW=b'fictional source fixture, not a provider original'
SHA=hashlib.sha256(RAW).hexdigest()
DAY='20261128'
RUN={'training_date':'2026-11-25','course':'WOOD','distance_m':1000,'elapsed_s':66.5}
OBJ={'schema':'kyoto_workout_canonical.v1','source':'OTHER_AUTHORIZED','day':DAY,'venue':'08','race':1,'original_sha256':SHA,'horses':[{'number':1,'name':'A','workouts':[RUN]},{'number':2,'name':'B','workouts':[RUN]}]}
def check(obj=OBJ, **override):
    raw=json.dumps(obj,ensure_ascii=False).encode()
    kw=dict(original=RAW,canonical=raw,expected_day=DAY,race_number=1,expected_roster={1:'A',2:'B'},verified_start_utc='2026-11-28T01:00:00Z',captured_utc='2026-11-27T02:00:00Z',expected_original_sha256=SHA,expected_canonical_sha256=hashlib.sha256(raw).hexdigest())
    kw.update(override);return inspect_workouts(**kw)
class Intake(unittest.TestCase):
    def test_full_roster_is_not_production_certification(self):
        r=check();self.assertEqual(r['canonical_valid_horses'],2);self.assertTrue(r['canonical_records_cover_roster']);self.assertFalse(r['production_coverage_authorized'])
    def test_missing_not_zero(self):
        x=copy.deepcopy(OBJ);x['horses'][1]['workouts']=[];r=check(x);self.assertEqual(r['canonical_valid_horses'],1);self.assertEqual(r['horses']['2']['state'],'MISSING')
    def test_wrong_name_isolated(self):
        x=copy.deepcopy(OBJ);x['horses'][1]['name']='C';r=check(x);self.assertEqual(r['horses']['2']['state'],'HORSE_IDENTITY_MISMATCH');self.assertEqual(r['canonical_valid_horses'],1)
    def test_wrong_meeting_identity(self):
        for key,value in [('race',2),('venue','05'),('day','20261129'),('original_sha256','b'*64)]:
            x=copy.deepcopy(OBJ);x[key]=value
            with self.assertRaisesRegex(ValueError,'canonical_identity'):check(x)
    def test_duplicate_or_extra_horse(self):
        for n in [1,3]:
            x=copy.deepcopy(OBJ);x['horses'][1]['number']=n
            with self.assertRaises(ValueError):check(x)
    def test_tampered_original(self):
        with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):check(original=RAW+b'X')
    def test_tampered_canonical(self):
        with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):check(expected_canonical_sha256='a'*64)
    def test_after_start_or_non_utc(self):
        for stamp in ['2026-11-28T01:00:00Z','2026-11-28T02:00:00Z','2026-11-27T02:00:00+09:00']:
            with self.assertRaises(ValueError):check(captured_utc=stamp)
    def test_late_training_rejected_per_horse(self):
        x=copy.deepcopy(OBJ);x['horses'][1]['workouts'][0]['training_date']='2026-11-28';r=check(x);self.assertEqual(r['horses']['2']['state'],'INVALID_WORKOUTS')
    def test_nonfinite_rejected(self):
        x=copy.deepcopy(OBJ);x['horses'][1]['workouts'][0]['elapsed_s']=float('nan')
        with self.assertRaisesRegex(ValueError,'nonfinite_json'):check(x)
    def test_bad_elapsed_or_duplicate(self):
        for n in [0,-2,True,9999]:
            x=copy.deepcopy(OBJ);x['horses'][1]['workouts'][0]['elapsed_s']=n
            self.assertEqual(check(x)['horses']['2']['state'],'INVALID_WORKOUTS')
        x=copy.deepcopy(OBJ);x['horses'][1]['workouts'].append(copy.deepcopy(RUN));self.assertEqual(check(x)['horses']['2']['state'],'INVALID_WORKOUTS')
    def test_deterministic_and_order_independent(self):
        x=copy.deepcopy(OBJ);x['horses'].reverse();a,b=check(),check(x)
        for n in ['1','2']:
            self.assertEqual(a['horses'][n]['value_digest'],b['horses'][n]['value_digest'])
        self.assertEqual(check(x),b)
