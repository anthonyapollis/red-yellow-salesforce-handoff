"""Generate a deterministic, intentionally dirty Salesforce-scale dataset.
Python 3.10+, standard library. Never connects to Salesforce.
"""
import argparse,csv,gzip,hashlib,io,json,math,time,collections
from pathlib import Path
from datetime import date,timedelta
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]
BASE={"Account":20000,"Contact":2000000,"Lead":1000000,"Campaign":2000,"CampaignMember":3000000,"Opportunity":500000,"RY_Programme_Enquiry__c":1500000,"RY_Application__c":400000,"RY_Student__c":300000,"RY_Enrolment__c":350000,"RY_Student_Progress__c":3500000}
PREFIX={"Account":"ACC","Contact":"CON","Lead":"LEAD","Campaign":"CAM","CampaignMember":"CM","Opportunity":"OPP","RY_Programme_Enquiry__c":"ENQ","RY_Application__c":"APP","RY_Student__c":"STU","RY_Enrolment__c":"ENR","RY_Student_Progress__c":"PRG","RY_Intake__c":"INT"}
def key(obj,i):return f"RYSCALE-{PREFIX[obj]}-{i:09d}"
FIRST=["Lerato","Thabo","Ayesha","Sipho","Naledi","Zanele","Fatima","David","Lwazi","Priya","Mpho","Siyanda","Nomsa","Imran","Kabelo","Emma","Nandi","Sizwe","Amina","Daniel","Buhle","Karabo","Chloe","Ravi"]
LAST=["Dlamini","Mokoena","Patel","Nkosi","Jacobs","Naidoo","Botha","Molefe","Khumalo","Williams","Petersen","Ndlovu","Maseko","Smith","Hassan","Adams"]
CITIES=["Cape Town","Johannesburg","Durban","Pretoria","Gqeberha","Bloemfontein","Polokwane","Kimberley"]
HEADERS={
"Account":["RY_External_ID__c","Name"],
"Contact":["RY_External_ID__c","FirstName","LastName","Email","Phone","MailingCity","MailingCountry","Account_Key"],
"Lead":["RY_External_ID__c","FirstName","LastName","Company","Email","Phone","City","Country","RY_Sample_Status__c"],
"Campaign":["RY_External_ID__c","Name","IsActive","StartDate","RY_Channel__c","RY_Spend_ZAR__c"],
"CampaignMember":["RY_External_ID__c","Campaign_Key","Contact_Key","Lead_Key"],
"Opportunity":["RY_External_ID__c","Name","Account_Key","Applicant_Key","Campaign_Key","Intake_Key","CloseDate","RY_Sample_Stage__c","RY_Expected_Value_ZAR__c"],
"RY_Programme_Enquiry__c":["RY_External_ID__c","Contact_Key","Lead_Key","Offering_Key","Enquiry_Date__c","Channel__c","Status__c"],
"RY_Application__c":["RY_External_ID__c","Contact_Key","Intake_Key","Opportunity_Key","Submitted_Date__c","Status__c","Decision_Date__c"],
"RY_Student__c":["RY_External_ID__c","Contact_Key","Student_Number__c"],
"RY_Enrolment__c":["RY_External_ID__c","Student_Key","Application_Key","Enrolled_Date__c","Status__c","Agreed_Fee_ZAR__c"],
"RY_Student_Progress__c":["RY_External_ID__c","Enrolment_Key","Week_Start__c","Attendance_Pct__c","Assessment_Average_Pct__c","Overdue_Assignments__c","Risk_Band__c"]}
def readrows(path):
 with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
class Model:
 def __init__(self,scale=1):
  if not (0<scale<=10):raise ValueError("scale must be >0 and <=10")
  self.counts={k:max(1,math.ceil(Decimal(n)*Decimal(str(scale)))) for k,n in BASE.items()}
  self.catalogue={}
  for obj in ("RY_Programme__c","RY_Programme_Offering__c"):
   self.catalogue[obj]=readrows(ROOT/"data/dirty_loadable"/(obj+".csv"))
  self.offers=[r["RY_External_ID__c"] for r in self.catalogue["RY_Programme_Offering__c"]]
  self.intakes=[];self.starts=[]
  for year in range(2015,2027):
   for month in (2,7):
    for offer in self.offers:
     n=len(self.intakes)+1;d=date(year,month,15)
     self.intakes.append({"RY_External_ID__c":key("RY_Intake__c",n),"Offering_Key":offer,"Start_Date__c":d.isoformat()});self.starts.append(d)
  self.catalogue["RY_Intake__c"]=self.intakes
  self.counts={**{o:len(rs) for o,rs in self.catalogue.items()},**self.counts}
 def intake(self,i):return (i*17-1)%len(self.intakes)+1
 def start(self,i):return self.starts[self.intake(i)-1]
 def student(self,i):return (i-1)%self.counts["RY_Student__c"]+1
 def contact(self,i):return self.student(i)
 def account(self,contact):return (contact-1)%self.counts["Account"]+1
 def person(self,i,kind):
  flags=[];base=i-1 if i%50==0 else i
  if base!=i:flags.append("business_duplicate_identity")
  first=FIRST[(base*7)%len(FIRST)];last=LAST[(base*11)%len(LAST)]
  email=f"{kind}{base:09d}@example.com"
  if i%17==0:email="";flags.append("missing_email")
  elif i%19==0:email=email.upper();flags.append("email_case")
  elif i%31==0:email=f"{kind}{base:09d}.typo@example.com";flags.append("suspect_email")
  if i%13==0:first=" "+first.lower()+" ";flags.append("name_whitespace_case")
  if i%23==0:last=last.upper();flags.append("surname_case")
  phone=f"+27 00 {base%10000000:07d}" # intentionally non-dialable area code
  if i%11==0:phone="";flags.append("missing_phone")
  elif i%7==0:phone=phone.replace(" ","-");flags.append("phone_format")
  city=CITIES[base%len(CITIES)]
  if i%29==0:city=city.upper()+" ";flags.append("city_format")
  country="South Africa"
  if i%9==0:country="ZA";flags.append("country_alias")
  return [first,last,email,phone,city,country],flags
 def row(self,obj,i):
  c=self.counts;flags=[];k=key(obj,i)
  if obj=="Account":
   name=f"DEMO Learning Sponsor {i:06d}"
   if i%25==0:name=f"demo learning sponsor {i-1:06d} ";flags.append("business_duplicate_name")
   return [k,name],flags
  if obj=="Contact":
   p,flags=self.person(i,"customer")
   return [k,*p,key("Account",self.account(i))],flags
  if obj=="Lead":
   p,flags=self.person(i,"prospect")
   if i%5==0:
    target=(i*7-1)%c["Contact"]+1
    q,_=self.person(target,"customer");p[0:3]=q[0:3];flags.append("cross_object_duplicate_identity")
   status="New enquiry" if i%7 else "new enqurey "
   if i%7==0:flags.append("status_typo")
   return [k,p[0],p[1],"DEMO Individual Applicant",p[2],p[3],p[4],p[5],status],flags
  if obj=="Campaign":
   name=f"DEMO Recruitment {i:05d}";channel=["Paid social","Email","Organic search","Webinar"][i%4]
   if i%13==0:channel=channel.lower().replace(" ","_")+" ";flags.append("channel_alias")
   if i%50==0:name=f"demo recruitment {i-1:05d} ";flags.append("business_duplicate_name")
   return [k,name,"false",date(2015+(i%12),1+(i%12),1).isoformat(),channel,5000+(i*137)%150000],flags
  if obj=="CampaignMember":
   if i<=c["Contact"]:
    who=key("Contact",i);lead=""
   else:who="";lead=key("Lead",(i-c["Contact"]-1)%c["Lead"]+1)
   return [k,key("Campaign",(i*7-1)%c["Campaign"]+1),who,lead],flags
  if obj=="Opportunity":
   person=self.contact(i);d=self.start(i)+timedelta(days=-14+(i%20));amount=4900+(i%13)*1000
   stage=["Enrolled","Application submitted","Offer accepted","Enquiry"][i%4]
   if i%37==0:amount*=10;flags.append("amount_outlier")
   if i%41==0:d=date(2099,1,1);flags.append("close_date_outlier")
   if i%17==0:stage="application submited ";flags.append("status_typo")
   return [k,f"DEMO Admission {i:09d}",key("Account",self.account(person)),key("Contact",person),key("Campaign",(i-1)%c["Campaign"]+1),key("RY_Intake__c",self.intake(i)),d.isoformat(),stage,amount],flags
  if obj=="RY_Programme_Enquiry__c":
   person=key("Contact",(i*11-1)%c["Contact"]+1) if i%5<3 else ""
   lead="" if person else key("Lead",(i*7-1)%c["Lead"]+1)
   channel=["Website","Paid social","Email","WhatsApp"][i%4]
   status="New" if i%3 else "Application received"
   if i%17==0:channel="web form ";flags.append("channel_alias")
   if i%19==0:status="new ";flags.append("status_case")
   return [k,person,lead,self.offers[(i-1)%len(self.offers)],(date(2015,1,1)+timedelta(days=i%4200)).isoformat(),channel,status],flags
  if obj=="RY_Application__c":
   submitted=self.start(i)-timedelta(days=45)
   accepted=i<=c["RY_Enrolment__c"]
   decision=(submitted+timedelta(days=14)).isoformat() if accepted else ""
   status="Accepted" if accepted else "Submitted"
   if accepted and i%43==0:decision=(submitted-timedelta(days=15)).isoformat();flags.append("decision_before_submission")
   if i%17==0:status=status.lower()+" ";flags.append("status_case")
   return [k,key("Contact",self.contact(i)),key("RY_Intake__c",self.intake(i)),key("Opportunity",i),submitted.isoformat(),status,decision],flags
  if obj=="RY_Student__c":
   number=f"DEMO-S{i:09d}"
   if i%23==0:number=" "+number.lower()+" ";flags.append("student_number_format")
   return [k,key("Contact",self.contact(i)),number],flags
  if obj=="RY_Enrolment__c":
   status="Registered";amount=4900+(i%13)*1000
   if i%17==0:status="REGISTRED ";flags.append("status_typo")
   if i%37==0:amount*=10;flags.append("fee_outlier")
   return [k,key("RY_Student__c",self.student(i)),key("RY_Application__c",i),(self.start(i)-timedelta(days=7)).isoformat(),status,amount],flags
  if obj=="RY_Student_Progress__c":
   enrol=(i-1)//10+1;week=(i-1)%10
   d=self.start(enrol);d=d-timedelta(days=d.weekday())+timedelta(weeks=week)
   attendance=40+(i*7)%61;mark=30+(i*11)%66;over=i%5;risk="High" if attendance<60 or mark<50 else "Low"
   if i%29==0:risk="Low" if risk=="High" else "High";flags.append("risk_evidence_mismatch")
   if i%31==0:mark=0;flags.append("zero_mark_placeholder")
   return [k,key("RY_Enrolment__c",enrol),d.isoformat(),attendance,mark,over,risk],flags
  raise KeyError(obj)
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for part in iter(lambda:f.read(1024*1024),b""):h.update(part)
 return h.hexdigest()
def generate(out,scale=1,shard_rows=100000):
 out=Path(out)
 if (out/"manifest.json").exists():raise ValueError("Completed dataset already exists; choose another output folder.")
 out.mkdir(parents=True,exist_ok=True)
 model=Model(scale);files=[];quality={};preview=out/"preview";preview.mkdir(exist_ok=True)
 start=time.monotonic()
 for obj,total in model.counts.items():
  headers=list(model.catalogue[obj][0]) if obj in model.catalogue else HEADERS[obj]
  flags_total=collections.Counter();affected=0;sample=[]
  for part,low in enumerate(range(1,total+1,shard_rows),1):
   high=min(low+shard_rows-1,total);rel=f"csv/{obj}/part-{part:05d}.csv.gz";path=out/rel;path.parent.mkdir(parents=True,exist_ok=True)
   uncompressed=0
   with path.open("wb") as raw,gzip.GzipFile(filename="",mode="wb",fileobj=raw,compresslevel=1,mtime=0) as gz:
    textbuf=io.StringIO(newline="");writer=csv.writer(textbuf,lineterminator="\n")
    writer.writerow(headers);data=textbuf.getvalue().encode();gz.write(data);uncompressed+=len(data)
    for i in range(low,high+1):
     if obj in model.catalogue:r=list(model.catalogue[obj][i-1].values());flags=[]
     else:r,flags=model.row(obj,i)
     if len(r)!=len(headers):raise AssertionError((obj,i,len(r),len(headers)))
     if flags:affected+=1;flags_total.update(flags)
     textbuf.seek(0);textbuf.truncate(0);writer.writerow(r);data=textbuf.getvalue().encode("utf-8");gz.write(data);uncompressed+=len(data)
     if i<=100:sample.append(r)
   if uncompressed>90_000_000:raise ValueError("Shard exceeds 90 MB; use smaller --shard-rows")
   files.append({"object":obj,"file":rel,"rows":high-low+1,"first_sequence":low,"last_sequence":high,"compressed_bytes":path.stat().st_size,"csv_bytes":uncompressed,"sha256":sha(path)})
   print(f"{obj}: {high:,}/{total:,}",flush=True)
  with (preview/(obj+".csv")).open("w",encoding="utf-8",newline="") as f:
   writer=csv.writer(f,lineterminator="\n");writer.writerow(headers);writer.writerows(sample)
  quality[obj]={"rows_with_injected_mutations":affected,"mutation_events":dict(flags_total),"note":"Catalogue retains small dirty seed; its issues are recorded in the repository's issue register." if obj in model.catalogue else "Flag counts may overlap on the same row."}
 manifest={"dataset":"Red & Yellow SYNTHETIC dirty scale test","version":"scale-v1","generator_scale":scale,"seed":"deterministic arithmetic v1","total_rows":sum(model.counts.values()),"counts":model.counts,"shard_rows":shard_rows,"files":files,"quality":quality,"elapsed_seconds":round(time.monotonic()-start,2),"synthetic_intakes":"2015-2026, two starts/year/offering; fabricated for load testing, not website facts","warning":"Not the institution's actual customer volume. Org storage and API capacity must be checked before Salesforce import."}
 (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
 (out/"README.txt").write_text("SYNTHETIC DIRTY SCALE DATA\nRead manifest.json for exact counts and checksums.\nCSV files are gzip compressed, UTF-8, with headers. Decompress one shard at a time.\nTransport *_Key columns need parent ID/external-ID relationship mapping before Salesforce import.\nSee the repository docs/SCALE_DATA_GUIDE.md and tools/prepare_scale_bulk.py.\nPreview files are excerpts and are not independently importable.\n",encoding="utf-8")
 print(json.dumps({"complete":True,"rows":manifest["total_rows"],"files":len(files),"seconds":manifest["elapsed_seconds"]}),flush=True)
 return manifest
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--output",required=True);p.add_argument("--scale",type=float,default=1);p.add_argument("--shard-rows",type=int,default=100000);a=p.parse_args()
 if a.shard_rows<1:raise SystemExit("shard rows must be positive")
 generate(a.output,a.scale,a.shard_rows)

