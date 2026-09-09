import csv,gzip,hashlib,json,sys,time
from pathlib import Path
d=Path(sys.argv[1]); m=json.loads((d/"manifest.json").read_text()); pref={"Account":"ACC","Contact":"CON","Lead":"LEAD","Campaign":"CAM","CampaignMember":"CM","Opportunity":"OPP","RY_Programme_Enquiry__c":"ENQ","RY_Application__c":"APP","RY_Student__c":"STU","RY_Enrolment__c":"ENR","RY_Student_Progress__c":"PRG","RY_Intake__c":"INT"}; counts={k:0 for k in m["counts"]}; total=0; t=time.monotonic()
for item in m["files"]:
 p=d/item["file"]; h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""): h.update(b)
 assert h.hexdigest()==item["sha256"],p
 n=0; obj=item["object"]
 with gzip.open(p,"rt",encoding="utf-8",newline="") as f:
  for r in csv.DictReader(f):
   n+=1; counts[obj]+=1
   if obj in pref: assert r["RY_External_ID__c"]==f"RYSCALE-{pref[obj]}-{counts[obj]:09d}"
   if obj in ("CampaignMember","RY_Programme_Enquiry__c"): assert bool(r["Contact_Key"]) != bool(r["Lead_Key"])
   if obj=="RY_Student_Progress__c": assert 0<=float(r["Attendance_Pct__c"])<=100 and 0<=float(r["Assessment_Average_Pct__c"])<=100
 assert n==item["rows"],(p,n,item["rows"]); total+=n; print(f"{obj}: {counts[obj]:,}",flush=True)
assert counts==m["counts"] and total==m["total_rows"]
out={"status":"PASS - FULL STREAMING STRUCTURAL CHECK","rows":total,"counts":counts,"shards":len(m["files"]),"seconds":round(time.monotonic()-t,2),"limitations":["Semantic defects intentionally remain","No Salesforce API calls were made"]}
(d/"validation.json").write_text(json.dumps(out,indent=2));print(json.dumps(out))
