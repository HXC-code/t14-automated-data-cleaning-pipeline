import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"exp"))
import run_exp as R
import pipeline2 as P
from tests.test_pipeline import mkrows
class V2Regression(unittest.TestCase):
 def test_r3_no_audit(self):
  rows=mkrows(30);rows[0]['capital_gain']=114.;audit=[]
  out,act=R.repair(rows,R.build_domain(rows),None,None,audit=audit)
  self.assertEqual(out[0]['capital_gain'],114.);self.assertFalse(audit)
 def test_unknown_range_review(self):
  rows=mkrows(30);rows[0]['age']=999.;q=[]
  out,_=R.repair(rows,R.build_domain(rows),None,None,review=q)
  self.assertEqual(out[0]['age'],999.);self.assertTrue(q)
 def test_reference_median_frozen(self):
  ref=mkrows(30,age=40.);rows=mkrows(30,age=80.);rows[0]['age']=None
  out,_=R.repair(rows,R.build_domain(rows),None,None,reference=ref,dedup=False)
  self.assertEqual(out[0]['age'],40.)
 def test_missing_categories_retained(self):
  rows=mkrows(30);rows[0]['native_country']=None;rows[0]['occupation']=None
  out,_=R.repair(rows,R.build_domain(rows),None,None,dedup=False)
  self.assertIsNone(out[0]['native_country']);self.assertIsNone(out[0]['occupation'])
 def test_noop_not_truth(self):
  rows=mkrows(100);dom=R.build_domain(rows);dirty,t,_=R.inject(rows,dom,.2,1)
  self.assertTrue(all(dirty[i][c]!=rows[i][c] for i,c in t))
 def test_features_frozen(self):
  ref=mkrows(30);dom=R.build_domain(ref);_,st=R.stat_scan(ref)
  a=P.cell_features(ref[:1],dom,{},st,R.EDU2NUM,reference=ref)[0]
  b=P.cell_features(ref[:1]+mkrows(30,workclass=None),dom,{},st,R.EDU2NUM,reference=ref)[0]
  self.assertEqual(a,b[:15])
 def test_gbdt_training_scale(self):
  x=[[i/10.] for i in range(100)];y=[int(i>=50) for i in range(100)]
  g=P.GBDT(rounds=10,min_leaf=5).fit(x,y);s=g.predict(x)
  self.assertGreater(R.auc(y,s),.99)
 def test_rule_subset(self):
  rows=mkrows(30);rows[0]['age']=999.
  self.assertFalse(R.rule_scan(rows,R.build_domain(rows),rules_on={'R0'}))
