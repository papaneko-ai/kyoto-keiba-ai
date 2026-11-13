"""R04 fixed 24-case offline model family acceptance."""
import copy,unittest,math
import test_p3_offline_model_tournament as fx
from diagnostics.p3_offline_model_tournament import TournamentRejected,predict
from diagnostics.p3_r04_model_families_lab import FAMILIES,pair_probabilities,train_and_compare
class R04FiveFamilyAcceptance(unittest.TestCase):
 def setUp(self):
  self.train=[fx.fixture(i) for i in range(1,7)]
  self.hold=[fx.fixture(i) for i in range(10,20)]
 def audit(self):return train_and_compare(self.train,self.hold,plan_locked_utc=fx.utc(30))
 def test_five_distinct_definitions(self):
  self.assertEqual(FAMILIES,("UNIFORM","PL_HARVILLE","BC_STYLE_PROXY","BENTER_STYLE_PROXY","ML_SOFTMAX"))
 def test_same_holdout_comparison(self):
  r=self.audit();self.assertEqual(set(r['holdout_proper_scores']),set(FAMILIES))
  self.assertTrue(all(x['holdout_races']==10 for x in r['holdout_proper_scores'].values()))
 def test_train_only_fit_receipts(self):
  r=self.audit();self.assertEqual(r['training_races'],6)
  self.assertTrue(all(x['training_candidates']>=1 for x in r['fitted_on_training_only'].values()))
  self.assertFalse(r['holdout_used_for_parameter_fitting'])
 def test_pl_uses_existing_canonical_prediction(self):
  s=self.hold[0]['snapshot'];src=predict(s,'PL_BASE')
  self.assertEqual(pair_probabilities(s,'PL_HARVILLE'),{tuple(row['pair']):row['probability'] for row in src['quinella']})
 def test_uniform_independent_of_strength(self):
  a=pair_probabilities(self.hold[0]['snapshot'],'UNIFORM')
  b=copy.deepcopy(self.hold[0]['snapshot']);b['runners'][0]['prior_strength']*=7
  self.assertEqual(a,pair_probabilities(b,'UNIFORM'))
 def test_bc_and_ml_are_distinct_from_pl(self):
  s=self.hold[0]['snapshot'];pl=pair_probabilities(s,'PL_HARVILLE')
  self.assertNotEqual(pl,pair_probabilities(s,'BC_STYLE_PROXY',1.5))
  self.assertNotEqual(pl,pair_probabilities(s,'ML_SOFTMAX',(1.,.5,.5)))
 def test_benter_endpoints(self):
  s=self.hold[0]['snapshot']
  a=pair_probabilities(s,'BENTER_STYLE_PROXY',1.)
  b=pair_probabilities(s,'PL_HARVILLE')
  self.assertTrue(all(abs(x-y)<1e-12 for x,y in zip(a.values(),b.values())))
  self.assertNotEqual(pair_probabilities(s,'BENTER_STYLE_PROXY',0.),b)
 def test_all_families_normalize(self):
  s=self.hold[0]['snapshot']
  params={'UNIFORM':None,'PL_HARVILLE':None,'BC_STYLE_PROXY':1.,'BENTER_STYLE_PROXY':.5,'ML_SOFTMAX':(1.,0.,0.)}
  for m in FAMILIES:
   q=pair_probabilities(s,m,params[m]);self.assertEqual(len(q),6);self.assertAlmostEqual(sum(q.values()),1.)
 def test_sixteen_runner_120_pairs(self):
  s=copy.deepcopy(self.hold[0]['snapshot'])
  s['runners']=[{'number':i,'frame':(i+1)//2,'prior_strength':float(19-i)} for i in range(1,17)]
  for m,p in [('UNIFORM',None),('PL_HARVILLE',None),('BC_STYLE_PROXY',1.),('BENTER_STYLE_PROXY',.5),('ML_SOFTMAX',(1.,0.,0.))]:
   q=pair_probabilities(s,m,p);self.assertEqual(len(q),120);self.assertAlmostEqual(sum(q.values()),1.)
 def test_replay_deterministic(self):self.assertEqual(self.audit(),self.audit())
 def test_final_receipt_changes_with_train_labels(self):
  a=self.audit()['receipt_sha256'];self.train[0]['winning_pair']=[2,3]
  self.assertNotEqual(a,self.audit()['receipt_sha256'])
 def test_holdout_labels_do_not_change_fitted_params(self):
  a=self.audit()['fitted_on_training_only'];self.hold[0]['winning_pair']=[2,3]
  self.assertEqual(a,self.audit()['fitted_on_training_only'])
 def test_holdout_scores_do_change_on_labels(self):
  a=self.audit()['holdout_proper_scores'];self.hold[0]['winning_pair']=[2,3]
  self.assertNotEqual(a,self.audit()['holdout_proper_scores'])
 def test_training_future_label_rejected(self):
  self.train[-1]['outcome_utc']=fx.utc(34)
  with self.assertRaisesRegex(TournamentRejected,'leakage'):self.audit()
 def test_train_holdout_overlap_rejected(self):
  self.hold[0]=copy.deepcopy(self.train[0])
  with self.assertRaisesRegex(TournamentRejected,'leakage'):self.audit()
 def test_duplicate_holdout_rejected(self):
  self.hold[1]['snapshot']['race_id']=self.hold[0]['snapshot']['race_id']
  with self.assertRaisesRegex(TournamentRejected,'leakage'):self.audit()
 def test_post_start_freeze_rejected(self):
  self.hold[0]['forecast_frozen_utc']=self.hold[0]['outcome_utc']
  with self.assertRaisesRegex(TournamentRejected,'leakage'):self.audit()
 def test_future_feature_rejected(self):
  self.hold[0]['snapshot']['feature_cutoff_utc']=self.hold[0]['snapshot']['race_start_utc']
  with self.assertRaisesRegex(TournamentRejected,'future_features'):self.audit()
 def test_nonlab_source_rejected(self):
  self.hold[0]['snapshot']['source_scope']='JRA_LIVE'
  with self.assertRaisesRegex(TournamentRejected,'nonlab'):self.audit()
 def test_unknown_family_rejected(self):
  with self.assertRaisesRegex(TournamentRejected,'unknown_r04_family'):
   pair_probabilities(self.hold[0]['snapshot'],'EXTRA')
 def test_invalid_parameters_rejected(self):
  for m,param in [('BC_STYLE_PROXY',-1),('BENTER_STYLE_PROXY',.32),('ML_SOFTMAX',(.3,0,0))]:
   with self.assertRaisesRegex(TournamentRejected,'r04_parameter_invalid'):
    pair_probabilities(self.hold[0]['snapshot'],m,param)
 def test_nonfinite_features_rejected(self):
  self.hold[0]['snapshot']['runners'][0]['prior_strength']=float('nan')
  with self.assertRaises(TournamentRejected):self.audit()
 def test_no_exact_formula_false_claim(self):
  r=self.audit()
  for k in ('benter_bc_exact_published_formulas_claimed','market_odds_were_used','official_jra_authenticated','real_calibration_certified','real_bet_authorized','holdout_winner_promoted_to_production'):
   self.assertFalse(r[k])
 def test_proper_scores_finite(self):
  for v in self.audit()['holdout_proper_scores'].values():
   self.assertTrue(math.isfinite(v['mean_multiclass_log_loss']))
   self.assertTrue(math.isfinite(v['mean_multiclass_brier']))
if __name__=='__main__':unittest.main()
