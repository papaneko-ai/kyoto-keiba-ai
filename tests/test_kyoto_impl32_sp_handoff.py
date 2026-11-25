import copy,unittest
from diagnostics.kyoto_impl32_sp_handoff import aggregate
from diagnostics.kyoto_impl31_handoff_budget import gather_bounded
from tests.test_kyoto_impl31_handoff_budget import fixture,DAY,REPO,run
from tests.test_kyoto_impl31_sp_saved_roster_audit import raw
from diagnostics.kyoto_impl31_sp_saved_roster_audit import inspect_heading

def source(numbers,roster='b'*64):
    return {'state':'VALID_ORIGINALS_WITH_INCOMPLETE_MARKETS','channel':'SP','day':DAY,
        'ciphertext_authenticated':True,'source_original_sha_utc_checked':True,
        'sp_saved_roster_audit':{'schema':'kyoto_impl31_sp_saved_roster_audit.v1','day':DAY,
        'live_acquisition_certified':False,'market_verified':False,'prestart_certified':False,
        'races':{str(n):({'state':'SP_STRUCTURAL_ROSTER_OBSERVED','runner_count':2,'source_sha256':'a'*64,
            'roster_sha256':roster,'captured_at_utc':'2026-11-28T01:00:00Z'} if n in numbers else {'state':'NO_VERIFIED_RAW_RACECARD'}) for n in range(1,13)}}}
def entry(i,ns,event='schedule',roster='b'*64):
    return {'run':run(i,event=event),'source_assessment':{'SP':source(ns,roster)}}
class SPHandoff(unittest.TestCase):
    def test_union_and_manual_separation(self):
        a=aggregate(DAY,[entry(1,range(1,7)),entry(2,range(7,13)),entry(3,[1],event='workflow_dispatch')])
        self.assertEqual(a['scheduled']['structural_roster_races'],12)
        self.assertEqual(a['manual']['structural_roster_races'],1)
        self.assertFalse(a['live_acquisition_certified']);self.assertFalse(a['pc_denominator_modified'])
    def test_conflicting_roster_not_counted(self):
        a=aggregate(DAY,[entry(1,[1,2]),entry(2,[1],roster='c'*64)])
        self.assertEqual(a['scheduled']['structural_roster_races'],1)
        self.assertEqual(a['scheduled']['races']['1']['state'],'SP_ROSTER_CONFLICT')
        self.assertEqual(len(a['scheduled']['races']['1']['observations']),2)
    def test_bad_auth_wrong_date_and_digest(self):
        e=entry(1,[1]);e['source_assessment']['SP']['ciphertext_authenticated']=False
        f=entry(2,[2]);f['source_assessment']['SP']['sp_saved_roster_audit']['races']['2']['captured_at_utc']='2026-11-29T01:00:00Z'
        g=entry(3,[3]);g['source_assessment']['SP']['sp_saved_roster_audit']['races']['3']['source_sha256']='bad'
        a=aggregate(DAY,[e,f,g]);self.assertEqual(a['scheduled']['structural_roster_races'],0);self.assertEqual(len(a['unavailable']),3)
    def test_idempotent_and_order_independent(self):
        x=[entry(1,[1]),entry(2,[1,2])];self.assertEqual(aggregate(DAY,x),aggregate(DAY,list(reversed(x))))
        with self.assertRaises(ValueError):aggregate(DAY,[x[0],x[0]])
    def test_real_handoff_route_no_pc_roster_promotion(self):
        def invoke(t,end):
            if t[0]=='lane' and t[-1]=='SP':return source([t[3]])
            return fixture(t,end)
        a=gather_bounded(DAY,REPO,invoke=invoke)
        self.assertEqual(a['independent_sp_source_coverage']['scheduled']['structural_roster_races'],4)
        self.assertEqual(a['independent_sp_source_coverage']['manual']['structural_roster_races'],1)
        self.assertEqual(a['day_source_coverage']['totals']['racecards'],0)
        self.assertFalse(a['full_live_jra_coverage_proved'])
    def test_utf8_cp932_same_roster_names(self):
        b=raw(1);self.assertEqual(inspect_heading(b,DAY,1),inspect_heading(b.decode('cp932').encode('utf8'),DAY,1))
        self.assertEqual(inspect_heading(b,DAY,1)[0][2],'馬A')
    def test_invalid_encoding_does_not_certify(self):
        with self.assertRaises(UnicodeError):inspect_heading(raw(1)+b'\x81',DAY,1)
if __name__=='__main__':unittest.main()
