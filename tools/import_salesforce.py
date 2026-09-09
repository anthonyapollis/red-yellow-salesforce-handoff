"""Salesforce seed importer. Python 3.10+, standard library only.
Default is offline validation. No writes unless --apply is supplied.
"""
import argparse,csv,json,os,sys,time
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import quote,urlparse
ROOT=Path(__file__).resolve().parents[1]
class StopRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise RuntimeError("Redirect refused; check Salesforce instance URL")
class API:
 def __init__(self,url,token,version):
  p=urlparse(url)
  if p.scheme!="https" or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ("","/"):raise ValueError("SF_INSTANCE_URL must be an HTTPS origin")
  self.base=url.rstrip("/")+"/services/data/v"+version
  self.token=token;self.opener=build_opener(StopRedirect)
 def call(self,method,path,payload=None,missing_ok=False):
  data=None if payload is None else json.dumps(payload).encode()
  req=Request(self.base+path,data=data,method=method,headers={"Authorization":"Bearer "+self.token,"Content-Type":"application/json"})
  for attempt in range(4):
   try:
    with self.opener.open(req,timeout=60) as r:
     raw=r.read();return json.loads(raw) if raw else {}
   except HTTPError as e:
    if e.code==404 and missing_ok:return None
    if e.code in (429,500,502,503,504) and attempt<3:
     time.sleep(2**attempt);continue
    body=e.read().decode(errors="replace")
    raise RuntimeError(f"{method} {path}: HTTP {e.code}: {body[:1500]}") from None
  raise RuntimeError("Request retry limit reached")
def load(root=ROOT,plan_path="salesforce/import_plan.json"):
 plans=json.loads((root/plan_path).read_text())
 rows={}
 for p in plans:
  with (root/p["file"]).open(encoding="utf-8",newline="") as handle:
   rows[p["object"]]=list(csv.DictReader(handle))
 return plans,rows
def validate(plans,rows,root=ROOT):
 schema=json.loads((root/"salesforce/schema.json").read_text())
 seen={};errors=[]
 for p in plans:
  obj=p["object"];seen[obj]={}
  types={x[0]:x[1] for x in schema[obj]}
  for n,r in enumerate(rows[obj],2):
   key=r.get(p["external_id"],"")
   if not key or key in seen[obj]:errors.append(f"{obj} row {n}: missing/duplicate external key")
   seen[obj][key]=r
   for f in p["required"]:
    if not r.get(f):errors.append(f"{obj}/{key}: missing {f}")
   for col,(fk,parent) in p["references"].items():
    if r.get(col) and r[col] not in seen.get(parent,{}):errors.append(f"{obj}/{key}: unresolved {col}={r[col]}")
   for field,value in r.items():
    if not value:continue
    typ=types.get(field)
    try:
     if typ in ("Number","Decimal"):
      num=float(value)
      if num<0:raise ValueError("negative")
      if typ=="Number" and not num.is_integer():raise ValueError("not integer")
      if field.endswith("_Pct__c") and num>100:raise ValueError("percentage >100")
     if typ=="Date":
      from datetime import date
      date.fromisoformat(value)
     if typ in ("Text","ExternalID") and len(value)>(100 if typ=="ExternalID" else 255):raise ValueError("too long")
    except ValueError as e:errors.append(f"{obj}/{key}: invalid {field}: {e}")
   if obj in ("CampaignMember","RY_Programme_Enquiry__c") and bool(r.get("Lead_Key"))==bool(r.get("Contact_Key")):errors.append(f"{obj}/{key}: require exactly one Lead_Key or Contact_Key")
   if obj=="RY_Programme_Offering__c":
    price=r.get("Advertised_Fee_ZAR__c")
    if (r["Price_Status__c"]=="Published")!=bool(price):errors.append(f"{obj}/{key}: price/status mismatch")
  if obj=="RY_Student__c":unique=["Contact_Key","Student_Number__c"]
  elif obj=="RY_Application__c":unique=["Opportunity_Key"]
  elif obj=="RY_Enrolment__c":unique=["Application_Key"]
  else:unique=[]
  for f in unique:
   vals=[r[f] for r in rows[obj] if r.get(f)]
   if len(vals)!=len(set(vals)):errors.append(f"{obj}: duplicate {f}")
  if obj=="RY_Student_Progress__c":
   pairs=[(r["Enrolment_Key"],r["Week_Start__c"]) for r in rows[obj]]
   if len(pairs)!=len(set(pairs)):errors.append("Duplicate enrolment/week progress")
 for r in rows.get("RY_Enrolment__c",[]):
  s=seen["RY_Student__c"].get(r["Student_Key"]);a=seen["RY_Application__c"].get(r["Application_Key"])
  if s and a and s["Contact_Key"]!=a["Contact_Key"]:errors.append("Enrolment student/applicant mismatch")
 for r in rows.get("RY_Application__c",[]):
  o=seen["Opportunity"].get(r["Opportunity_Key"])
  if o and (o["Applicant_Key"]!=r["Contact_Key"] or o["Intake_Key"]!=r["Intake_Key"]):errors.append("Application/opportunity applicant or intake mismatch")
 if errors:raise ValueError("\n".join(errors))
 return {p["object"]:len(rows[p["object"]]) for p in plans}
def scalar(value,field):
 typ=field.get("type")
 if typ in ("double","currency","percent"):return float(value)
 if typ=="int":return int(value)
 if typ=="boolean":
  if value.lower() not in ("true","false"):raise ValueError("Invalid boolean")
  return value.lower()=="true"
 return value
def payload(plan,row,describes,idmap,stage):
 obj=plan["object"];fs={f["name"]:f for f in describes[obj]["fields"]}
 result={}
 for col,value in row.items():
  if value=="":continue # Unknowns do not overwrite an existing value with null.
  if col in plan["references"]:
   field,parent=plan["references"][col]
   result[field]=idmap[parent][value]
  else:
   if col not in fs:raise ValueError(f"{obj}.{col} missing")
   result[col]=scalar(value,fs[col])
 if obj=="Opportunity":result["StageName"]=stage
 return result
def preflight(api,plans,rows,stage):
 describes={}
 for p in plans:
  obj=p["object"];d=api.call("GET",f"/sobjects/{obj}/describe")
  if not d.get("createable") or not d.get("updateable"):raise ValueError(f"{obj} needs create/update access")
  fs={f["name"]:f for f in d["fields"]};ext=fs.get(p["external_id"],{})
  if not ext.get("externalId") or not ext.get("unique"):raise ValueError(f"{obj} external ID must be unique")
  sent=set()
  for r in rows[obj]:
   for col,val in r.items():
    if val!="":sent.add(p["references"].get(col,[col])[0])
  if obj=="Opportunity":sent.add("StageName")
  for f in sent:
   if f not in fs or not fs[f].get("createable"):raise ValueError(f"{obj}.{f} unavailable/not createable")
  for f in fs.values():
   if f.get("createable") and not f.get("nillable") and not f.get("defaultedOnCreate") and not f.get("autoNumber") and f["name"] not in sent:
    raise ValueError(f"{obj}: required org field {f['name']} is not in seed; map before importing")
  if obj=="Opportunity":
   values=[v["value"] for v in fs["StageName"].get("picklistValues",[]) if v.get("active")]
   if stage not in values:raise ValueError("Supply --opportunity-stage with an active org value: "+", ".join(values))
  describes[obj]=d
 return describes
def run(args):
 plans,rows=load(plan_path=args.plan)
 counts=validate(plans,rows)
 selected=[p for p in plans if p["group"]=="catalogue" or args.include_demo]
 print(json.dumps({"offline_validation":"PASS","selected_counts":{p["object"]:counts[p["object"]] for p in selected}},indent=2))
 if not (args.preflight or args.apply):return
 url=os.environ.get("SF_INSTANCE_URL","");token=os.environ.get("SF_ACCESS_TOKEN","")
 if not url or not token:raise ValueError("Set SF_INSTANCE_URL and SF_ACCESS_TOKEN in your environment; never put credentials in this ZIP.")
 api=API(url,token,args.api_version)
 describes=preflight(api,selected,rows,args.opportunity_stage)
 print("Read-only org preflight passed. Org validation rules, flows and record-type constraints may still reject records.")
 if not args.apply:return
 if not args.expected_host or urlparse(url).hostname!=args.expected_host:raise ValueError("--expected-host must exactly match SF_INSTANCE_URL host")
 ids={};log=[];reportdir=ROOT/"run_results";reportdir.mkdir(exist_ok=True)
 try:
  for p in selected:
   obj=p["object"];ids[obj]={};fs={f["name"]:f for f in describes[obj]["fields"]}
   for r in rows[obj]:
    key=r[p["external_id"]];path=f"/sobjects/{obj}/{p['external_id']}/{quote(key,safe='')}"
    current=api.call("GET",path,missing_ok=True)
    body=payload(p,r,describes,ids,args.opportunity_stage)
    if current:
     for f in list(body):
      if not fs[f].get("updateable"):
       if current.get(f)!=body[f]:raise ValueError(f"{obj}/{key}: immutable field {f} differs; manual reconciliation required")
       del body[f]
    result=api.call("PATCH",path,body)
    rid=(result or {}).get("id") or (current or {}).get("Id")
    if not rid:rid=api.call("GET",path)["Id"]
    ids[obj][key]=rid
    log.append({"object":obj,"external_key":key,"salesforce_id":rid,"operation":"updated" if current else "created"})
    (reportdir/"import_log.json").write_text(json.dumps(log,indent=2))
  (reportdir/"id_map.json").write_text(json.dumps(ids,indent=2))
  print(f"Imported {len(log)} records. Results saved under run_results/.")
 except Exception:
  (reportdir/"id_map.partial.json").write_text(json.dumps(ids,indent=2))
  print(f"Stopped after {len(log)} successful writes. No automatic rollback. Fix and rerun; preserve external IDs.",file=sys.stderr)
  raise
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--include-demo",action="store_true",help="Include explicitly fictional CRM/student records")
 p.add_argument("--preflight",action="store_true",help="Read org metadata; no data writes")
 p.add_argument("--apply",action="store_true",help="Actually upsert the selected data")
 p.add_argument("--expected-host",help="Exact target Salesforce hostname, required for --apply")
 p.add_argument("--opportunity-stage",default="",help="Existing Salesforce StageName for all demo opportunities; sample business stages remain in RY_Sample_Stage__c")
 p.add_argument("--plan",default="salesforce/import_plan.json",help="Import plan to run; use data/crm_load/import_plan.json for the generated CRM slice")
 p.add_argument("--api-version",default="66.0")
 args=p.parse_args()
 try:run(args)
 except Exception as e:print("ERROR: "+str(e),file=sys.stderr);sys.exit(1)
if __name__=="__main__":main()

