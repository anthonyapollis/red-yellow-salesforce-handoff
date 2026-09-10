from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "ebook" / "screenshots" / "03_Canonical_ERD.png"
W, H = 2400, 1800
BG = "#FFF9F0"
CHARCOAL = "#1D1D1B"
SLATE = "#60646B"
RED = "#F52635"
YELLOW = "#FFB71B"
TEAL = "#007C83"
RULE = "#C8CFD6"
WHITE = "#FFFFFF"

def font(size, bold=False):
    paths = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

F_TITLE = font(58, True)
F_SUB = font(26)
F_LANE = font(28, True)
F_NODE = font(27, True)
F_NODE_SUB = font(19)
F_REL = font(20)
F_FOOT = font(19)

im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)

def rounded(box, fill, outline=RULE, radius=18, width=3):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def centered(text, box, f, fill=CHARCOAL):
    x0,y0,x1,y1 = box
    bb = d.multiline_textbbox((0,0), text, font=f, spacing=3, align="center")
    tw,th = bb[2]-bb[0], bb[3]-bb[1]
    d.multiline_text(((x0+x1-tw)/2, (y0+y1-th)/2), text, font=f, fill=fill, spacing=3, align="center")

d.text((80, 38), "Red & Yellow canonical data model", font=F_TITLE, fill=RED)
d.text((82, 105), "A clean relationship map for catalogue, CRM acquisition and the learner lifecycle. Full relationship registry below.", font=F_SUB, fill=SLATE)

lanes = [
    (70, 155, 590, 1320, "CATALOGUE", YELLOW),
    (700, 155, 1340, 1320, "CRM AND ACQUISITION", TEAL),
    (1380, 155, 2330, 1320, "ADMISSIONS AND LEARNER LIFECYCLE", RED),
]
for x0,y0,x1,y1,label,color in lanes:
    rounded((x0,y0,x1,y1), "#FFFDF8", RULE, 20, 2)
    d.rounded_rectangle((x0,y0,x1,y0+64), radius=20, fill=color)
    d.rectangle((x0,y0+32,x1,y0+64), fill=color)
    centered(label, (x0,y0+4,x1,y0+60), F_LANE, WHITE)

nodes = {
    "Programme": (125, 275, 535, 370, "PROGRAMME", "83 exact-name records", YELLOW),
    "Offering": (125, 490, 535, 585, "OFFERING", "89 catalogue listings", YELLOW),
    "Intake": (125, 705, 535, 800, "INTAKE", "47 observed start dates", YELLOW),
    "Account": (765, 225, 1275, 315, "ACCOUNT", "CRM organisation", TEAL),
    "Contact": (765, 385, 1275, 475, "CONTACT", "golden CRM identity", TEAL),
    "Lead": (765, 545, 1275, 635, "LEAD", "prospect identity", TEAL),
    "Campaign": (765, 705, 1275, 795, "CAMPAIGN", "channel and spend", TEAL),
    "CampaignMember": (765, 865, 1275, 955, "CAMPAIGN MEMBER", "contact or lead participation", TEAL),
    "Opportunity": (1450, 225, 2260, 315, "OPPORTUNITY", "applicant and target intake", RED),
    "Enquiry": (1450, 405, 2260, 495, "PROGRAMME ENQUIRY", "interest in an offering", RED),
    "Application": (1450, 585, 2260, 675, "APPLICATION", "decision for intake", RED),
    "Student": (1450, 765, 2260, 855, "STUDENT", "academic-system identity", RED),
    "Enrolment": (1450, 945, 2260, 1035, "ENROLMENT", "student joins application", RED),
    "Progress": (1450, 1125, 2260, 1215, "STUDENT PROGRESS", "one record per week", RED),
}
for key,(x0,y0,x1,y1,title,sub,color) in nodes.items():
    rounded((x0,y0,x1,y1), WHITE, color, 15, 4)
    d.rounded_rectangle((x0,y0,x1,y0+10), radius=12, fill=color)
    d.rectangle((x0,y0+5,x1,y0+10), fill=color)
    d.text((x0+24,y0+24), title, font=F_NODE, fill=CHARCOAL)
    d.text((x0+24,y0+60), sub, font=F_NODE_SUB, fill=SLATE)

def pt(key, side):
    x0,y0,x1,y1,*_ = nodes[key]
    return (x1 if side == "r" else x0, (y0+y1)//2)

def arrow_head(p1, p2, color):
    x1,y1 = p1; x2,y2 = p2
    size = 13
    if abs(x2-x1) >= abs(y2-y1):
        sign = 1 if x2 >= x1 else -1
        poly = [(x2,y2), (x2-sign*size,y2-size//2), (x2-sign*size,y2+size//2)]
    else:
        sign = 1 if y2 >= y1 else -1
        poly = [(x2,y2), (x2-size//2,y2-sign*size), (x2+size//2,y2-sign*size)]
    d.polygon(poly, fill=color)

def edge(a,b,color=SLATE,dashed=False,bend=None):
    p1 = pt(a,"r"); p2 = pt(b,"l")
    path = [p1,p2] if bend is None else [p1,(bend,p1[1]),(bend,p2[1]),p2]
    for start,end in zip(path,path[1:]):
        if dashed:
            x1,y1=start; x2,y2=end
            dist=max(abs(x2-x1),abs(y2-y1)); steps=max(1,int(dist/28))
            for i in range(0,steps,2):
                a0=i/steps; a1=min((i+1)/steps,1)
                q1=(x1+(x2-x1)*a0,y1+(y2-y1)*a0)
                q2=(x1+(x2-x1)*a1,y1+(y2-y1)*a1)
                d.line((q1,q2), fill=color, width=3)
        else:
            d.line((start,end), fill=color, width=3)
    arrow_head(path[-2], path[-1], color)

edge("Programme","Offering",YELLOW,bend=600)
edge("Offering","Intake",YELLOW,bend=620)
edge("Account","Contact",TEAL,bend=1320)
edge("Account","Opportunity",TEAL,bend=1360)
edge("Contact","Lead",TEAL,bend=1300)
edge("Campaign","CampaignMember",TEAL,bend=1280)
edge("Lead","CampaignMember",TEAL,bend=1320,dashed=True)
edge("Contact","CampaignMember",TEAL,bend=1360,dashed=True)
edge("Contact","Opportunity",TEAL,bend=1380)
edge("Campaign","Opportunity",TEAL,bend=1420,dashed=True)
edge("Intake","Opportunity",YELLOW,bend=1340,dashed=True)
edge("Contact","Enquiry",TEAL,bend=1400,dashed=True)
edge("Lead","Enquiry",TEAL,bend=1440,dashed=True)
edge("Offering","Enquiry",YELLOW,bend=1380)
edge("Contact","Application",TEAL,bend=1410)
edge("Intake","Application",YELLOW,bend=1360)
edge("Opportunity","Application",RED,bend=2310,dashed=True)
edge("Contact","Student",TEAL,bend=1390,dashed=True)
edge("Student","Enrolment",RED,bend=2310)
edge("Application","Enrolment",RED,bend=2300,dashed=True)
edge("Enrolment","Progress",RED,bend=2310)

ry = 1375
d.text((90, ry), "Relationship registry", font=F_LANE, fill=CHARCOAL)
d.text((90, ry+42), "Solid arrows show the parent-to-child path. Dashed arrows are optional lookups or conversion links.", font=F_SUB, fill=SLATE)
relations = [
    "Programme 1:N Offering", "Offering 1:N Intake",
    "Account 0..1:N Contact", "Account 0..1:N Opportunity",
    "Campaign 1:N CampaignMember", "Lead 0..1:N CampaignMember",
    "Contact 0..1:N CampaignMember", "Contact 0..1:N Lead (converted)",
    "Contact 1:N Opportunity", "Campaign 0..1:N Opportunity",
    "Intake 0..1:N Opportunity", "Contact 0..1:N Enquiry",
    "Lead 0..1:N Enquiry", "Offering 1:N Enquiry",
    "Contact 1:N Application", "Intake 1:N Application",
    "Opportunity 1:0..1 Application", "Contact 0..1:1 Student",
    "Student 1:N Enrolment", "Application 1:0..1 Enrolment",
    "Enrolment 1:N Student Progress",
]
cols = [90, 860, 1630]
for i, rel in enumerate(relations):
    col = i // 7
    row = i % 7
    x = cols[col]
    y = ry + 92 + row*36
    d.text((x,y), rel, font=F_REL, fill=CHARCOAL)

d.text((90, 1740), "Catalogue source: public Red & Yellow screenshots. CRM and learner records are synthetic demonstration data.", font=F_FOOT, fill=SLATE)
im.save(OUT, format="PNG", optimize=True)
print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
