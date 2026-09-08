"""Focused offline tests; no Salesforce calls."""
import unittest,copy,json,csv
from pathlib import Path
import import_salesforce as m
class ImportTests(unittest.TestCase):
 def setUp(self):self.plans,self.rows=m.load()
 def test_valid_package(self):
  counts=m.validate(self.plans,self.rows)
  self.assertEqual(counts["RY_Programme_Offering__c"],89)
  self.assertEqual(counts["RY_Intake__c"],47)
 def test_broken_parent_rejected(self):
  self.rows["RY_Intake__c"][0]["Offering_Key"]="MISSING"
  with self.assertRaisesRegex(ValueError,"unresolved"):m.validate(self.plans,self.rows)
 def test_campaign_member_xor(self):
  self.rows["CampaignMember"][0]["Lead_Key"]="RY-DEMO-LEAD-001"
  with self.assertRaisesRegex(ValueError,"exactly one"):m.validate(self.plans,self.rows)
 def test_duplicate_key_rejected(self):
  self.rows["Contact"].append(copy.deepcopy(self.rows["Contact"][0]))
  with self.assertRaisesRegex(ValueError,"duplicate"):m.validate(self.plans,self.rows)
 def test_progress_grain_rejected(self):
  r=copy.deepcopy(self.rows["RY_Student_Progress__c"][0]);r["RY_External_ID__c"]="RY-DEMO-PROG-099"
  self.rows["RY_Student_Progress__c"].append(r)
  with self.assertRaisesRegex(ValueError,"enrolment/week"):m.validate(self.plans,self.rows)
 def test_percent_range_rejected(self):
  self.rows["RY_Student_Progress__c"][0]["Attendance_Pct__c"]="101"
  with self.assertRaisesRegex(ValueError,"percentage"):m.validate(self.plans,self.rows)
 def test_enquire_not_zero(self):
  r=next(x for x in self.rows["RY_Programme_Offering__c"] if x["Price_Status__c"]=="Enquire")
  r["Advertised_Fee_ZAR__c"]="0"
  with self.assertRaisesRegex(ValueError,"price/status"):m.validate(self.plans,self.rows)
 def test_student_application_consistency(self):
  self.rows["RY_Enrolment__c"][0]["Student_Key"]="RY-DEMO-STU-003"
  with self.assertRaisesRegex(ValueError,"student/applicant"):m.validate(self.plans,self.rows)
 def test_payload_resolves_parent_and_numeric_and_omits_blank(self):
  p=next(p for p in self.plans if p["object"]=="RY_Programme_Offering__c")
  r=copy.deepcopy(self.rows[p["object"]][0]);r["Advertised_Fee_ZAR__c"]="13500";r["Notes__c"]=""
  schema=json.loads((m.ROOT/"salesforce/schema.json").read_text())
  fields=[{"name":f[0],"type":{"Number":"int","Decimal":"double"}.get(f[1],"string")} for f in schema[p["object"]]]
  result=m.payload(p,r,{p["object"]:{"fields":fields}},{"RY_Programme__c":{r["Programme_Key"]:"a00000000000001AAA"}},"")
  self.assertEqual(result["Programme__c"],"a00000000000001AAA")
  self.assertEqual(result["Advertised_Fee_ZAR__c"],13500.0)
  self.assertNotIn("Programme_Key",result);self.assertNotIn("Notes__c",result)
 def test_plain_http_rejected(self):
  with self.assertRaises(ValueError):m.API("http://example.com","unused","66.0")
if __name__=="__main__":unittest.main(verbosity=2)

