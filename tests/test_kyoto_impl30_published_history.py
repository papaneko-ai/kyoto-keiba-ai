"""Published-source evidence is separate from explicit finality/settlement."""
import copy,unittest
from diagnostics.kyoto_impl30_postrace_replay import published_history
from diagnostics.kyoto_impl30_day_coverage import combine,include_postrace,digest,proof
from tests.test_kyoto_impl30_final_reconcile import DAY,START,STAMP,ROSTER

def observation(run_id='101',price=400,stamp=STAMP,correction=False):
    return {'run_id':run_id,'observation':{
        'day':DAY,'race':1,'state':'DUAL_PAGE_MATCH_FINALITY_UNPROVEN',
        'result_sha256':'a'*64,'payout_sha256':'b'*64,
        'result_utc':stamp,'payout_utc':stamp,
        'markets':{'quinella':{'payout_per_100':{'1-2':price},'refunded_pairs':[]},
                   'bracket_quinella':{'payout_per_100':{'1-2':300},'refunded_pairs':[]}},
        'official_payout_publication_verified':True,'correction':correction,
        'settlement_authorized':False}}

class PublishedHistoryTests(unittest.TestCase):
    def chain(self,entries):return published_history(entries,day=DAY,race=1)
    def test_deterministic_and_preserves_observation_order(self):
        a=observation();b=observation('102',stamp='2026-11-28T13:00:00Z')
        before=copy.deepcopy([a,b]);r=self.chain([b,a])
        self.assertEqual(r,self.chain([a,b]))
        self.assertEqual([a,b],before)
        self.assertEqual(r['state'],'OFFICIAL_PUBLISHED_PAYOUT_CHAIN')
        self.assertEqual(r['revisions'][1]['previous_sha256'],r['revisions'][0]['sha256'])
        self.assertFalse(r['settlement_authorized'])
    def test_conflict_and_correction(self):
        a=observation();b=observation('102',price=500,stamp='2026-11-28T13:00:00Z')
        self.assertEqual(self.chain([a,b])['state'],'CONFLICT')
        b['observation']['correction']=True
        self.assertEqual(self.chain([a,b])['state'],'OFFICIAL_PUBLISHED_PAYOUT_CHAIN')
        b['observation']['payout_utc']=STAMP
        self.assertEqual(self.chain([a,b])['state'],'CONFLICT')
    def test_unverified_identity_and_duplicate(self):
        a=observation()
        self.assertEqual(self.chain([a,a])['state'],'CONFLICT')
        for field,value in [('race',2),('day','20261129'),('official_payout_publication_verified',False),('settlement_authorized',True),('payout_sha256','a'*64)]:
            b=copy.deepcopy(a);b['observation'][field]=value
            self.assertEqual(self.chain([b])['state'],'CONFLICT')
    def test_coverage_only_for_complete_nonconflicting_chain(self):
        slot={'day':DAY,'run_id':'100','races':{'1':{
            'roster_digest':'roster','named_roster_digest':digest(ROSTER),'start_utc':START,
            'racecard':proof('c'*64,'2026-11-28T04:00:00Z','roster'),
            'horses':{str(n):{} for n,_,_ in ROSTER},'track':{},'markets':{}}}}
        coverage=combine(DAY,[slot])
        replay={'schema':'kyoto_impl30_postrace_replay.v1','day':DAY,
            'prior_artifact_index_complete':True,'races':{},
            'published_payout_chains':{'1':self.chain([observation()])}}
        def read():return include_postrace(coverage,replay,roster={1:ROSTER},starts={1:START})
        r=read()
        self.assertEqual(r['totals']['official_published_payout'],1)
        self.assertEqual(r['totals']['official_payout'],0)
        self.assertFalse(r['races']['1']['postrace']['settlement_authorized'])
        replay['prior_artifact_index_complete']=False
        self.assertEqual(read()['totals']['official_published_payout'],0)
        replay['prior_artifact_index_complete']=True
        replay['published_payout_chains']['1']=self.chain([observation(),observation('102',price=500)])
        self.assertEqual(read()['totals']['official_published_payout'],0)
        self.assertEqual(read()['races']['1']['postrace']['state'],'PUBLISHED_PAYOUT_CONFLICT')

if __name__=='__main__':unittest.main()
