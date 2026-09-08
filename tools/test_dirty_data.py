import unittest,csv,json,copy
from pathlib import Path
import import_salesforce as m
class DirtyDataTests(unittest.TestCase):
 def setUp(self):
  self.plans,self.rows=m.load()
  self.issues=list(csv.DictReader((m.ROOT/"data/quality/ISSUE_REGISTER.csv").read_text().splitlines()))
 def test_dirty_is_default(self):
  self.assertTrue(all("/dirty_loadable/" in p["file"] for p in self.plans))
  self.assertTrue(all(r["RY_External_ID__c"].startswith("RY-DIRTY-") for rs in self.rows.values() for r in rs))
 def test_loadable_structure_passes(self):
  counts=m.validate(self.plans,self.rows)
  self.assertEqual(sum(counts.values()),253)
 def test_business_duplicates_retained(self):
  rs=self.rows["Contact"]
  emails=[r["Email"].strip().casefold() for r in rs if r["Email"]]
  self.assertGreater(len(emails),len(set(emails)))
  intakes=self.rows["RY_Intake__c"]
  pairs=[(r["Offering_Key"],r["Start_Date__c"]) for r in intakes]
  self.assertGreater(len(pairs),len(set(pairs)))
 def test_semantic_defects_retained(self):
  self.assertTrue(any(float(r["Advertised_Fee_ZAR__c"] or 0)>100000 for r in self.rows["RY_Programme_Offering__c"]))
  self.assertTrue(any(r["Decision_Date__c"] and r["Decision_Date__c"]<r["Submitted_Date__c"] for r in self.rows["RY_Application__c"]))
  self.assertTrue(any(not r["Email"] for r in self.rows["Contact"]))
 def test_raw_rejected(self):
  raw={p["object"]:list(csv.DictReader((m.ROOT/"data/dirty_raw"/(p["object"]+".csv")).read_text().splitlines())) for p in self.plans}
  with self.assertRaisesRegex(ValueError,"unresolved|invalid|duplicate"):m.validate(self.plans,raw)
 def test_issue_register_complete(self):
  self.assertEqual(len(self.issues),81)
  self.assertEqual(sum(r["dataset"]=="dirty_loadable" for r in self.issues),66)
  self.assertEqual(sum(r["dataset"]=="dirty_raw" for r in self.issues),15)
  self.assertTrue(all(r["provenance"].startswith("Deliberately injected") for r in self.issues))
 def test_reference_catalogue_unchanged(self):
  reference=json.loads((m.ROOT/"data/reference_clean/all_records.json").read_text())
  self.assertEqual(len(reference["RY_Programme_Offering__c"]),89)
  clean=next(r for r in reference["RY_Programme_Offering__c"] if r["Title__c"]=="Data Analysis")
  self.assertEqual(clean["Advertised_Fee_ZAR__c"],"13500")
 def test_payload_keeps_dirt(self):
  p=next(p for p in self.plans if p["object"]=="Contact")
  r=self.rows["Contact"][0]
  fields=[{"name":k,"type":"string"} for k in r if k!="Account_Key"]+[{"name":"AccountId","type":"reference"}]
  result=m.payload(p,r,{"Contact":{"fields":fields}},{"Account":{r["Account_Key"]:"001000000000001AAA"}},"")
  self.assertEqual(result["FirstName"]," lerato ")
  self.assertEqual(result["LastName"],"DLAMINI")
if __name__=="__main__":unittest.main(verbosity=2)

