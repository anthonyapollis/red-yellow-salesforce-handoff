"""South African reference data for the Red & Yellow synthetic generator.

Names, domains, provinces and channels are drawn from realistic SA distributions
so the generated CRM looks like a Cape Town education provider's actual pipeline
rather than Faker's US defaults.
"""

# Weighted to roughly reflect SA population/language groups. Not a census.
FIRST_NAMES = [
    ("Thabo", 34), ("Lerato", 33), ("Sipho", 30), ("Nomsa", 29), ("Bongani", 27),
    ("Zanele", 27), ("Mandla", 24), ("Nokuthula", 23), ("Tshepo", 23), ("Palesa", 22),
    ("Kagiso", 21), ("Refilwe", 20), ("Sibusiso", 20), ("Ayanda", 26), ("Thandiwe", 22),
    ("Katlego", 19), ("Mpho", 25), ("Lindiwe", 21), ("Themba", 19), ("Naledi", 21),
    ("Nkosinathi", 16), ("Busisiwe", 17), ("Andile", 18), ("Zodwa", 14), ("Lwazi", 15),
    ("Johan", 18), ("Pieter", 16), ("Anmarie", 9), ("Riaan", 12), ("Marlize", 9),
    ("Willem", 12), ("Elmarie", 9), ("Hendrik", 11), ("Chantelle", 12), ("Dewald", 8),
    ("Michael", 17), ("Sarah", 15), ("David", 14), ("Emma", 12), ("James", 13),
    ("Kirsten", 10), ("Ryan", 12), ("Megan", 12), ("Daniel", 13), ("Jessica", 12),
    ("Priya", 10), ("Rajesh", 8), ("Ashwin", 8), ("Nadia", 10), ("Yusuf", 11),
    ("Fatima", 11), ("Zaid", 8), ("Aisha", 9), ("Tariq", 7), ("Shireen", 8),
    ("Chad", 8), ("Tarryn", 8), ("Kyle", 9), ("Roche", 6), ("Ilse", 6),
]

SURNAMES = [
    ("Nkosi", 30), ("Dlamini", 30), ("Mokoena", 26), ("Khumalo", 25), ("Ndlovu", 26),
    ("Mahlangu", 22), ("Sithole", 22), ("Molefe", 20), ("Zulu", 20), ("Mthembu", 21),
    ("Mabaso", 16), ("Nyathi", 15), ("Radebe", 17), ("Sibiya", 16), ("Maseko", 17),
    ("Van der Merwe", 20), ("Botha", 18), ("Van Wyk", 17), ("Pretorius", 15),
    ("Nel", 14), ("Steyn", 14), ("Fourie", 13), ("Du Plessis", 15), ("Venter", 13),
    ("Naidoo", 18), ("Pillay", 17), ("Govender", 16), ("Reddy", 14), ("Moodley", 13),
    ("Adams", 16), ("Abrahams", 15), ("September", 12), ("Petersen", 14), ("Jacobs", 15),
    ("Damons", 10), ("Hendricks", 14), ("Isaacs", 12), ("Daniels", 13), ("Fortuin", 10),
    ("Smith", 14), ("Williams", 15), ("Jansen", 12), ("Nortje", 9), ("Coetzee", 13),
]

# Free consumer mail dominates SA education enquiries; .co.za corporates trail.
EMAIL_DOMAINS = [
    ("gmail.com", 52), ("outlook.com", 12), ("yahoo.com", 6), ("icloud.com", 5),
    ("hotmail.com", 6), ("webmail.co.za", 4), ("mweb.co.za", 3), ("telkomsa.net", 2),
    ("vodamail.co.za", 2), ("live.co.za", 2), ("gmail.co.za", 1), ("outlook.co.za", 1),
]

PROVINCES = [
    ("Western Cape", 30), ("Gauteng", 34), ("KwaZulu-Natal", 13), ("Eastern Cape", 7),
    ("Free State", 4), ("Limpopo", 4), ("Mpumalanga", 4), ("North West", 2),
    ("Northern Cape", 1), ("Outside South Africa", 1),
]

CITY_BY_PROVINCE = {
    "Western Cape": ["Cape Town", "Stellenbosch", "Paarl", "George", "Somerset West", "Bellville"],
    "Gauteng": ["Johannesburg", "Pretoria", "Sandton", "Centurion", "Midrand", "Soweto", "Benoni"],
    "KwaZulu-Natal": ["Durban", "Pietermaritzburg", "Umhlanga", "Ballito", "Richards Bay"],
    "Eastern Cape": ["Gqeberha", "East London", "Mthatha", "Makhanda"],
    "Free State": ["Bloemfontein", "Welkom", "Bethlehem"],
    "Limpopo": ["Polokwane", "Tzaneen", "Mokopane"],
    "Mpumalanga": ["Mbombela", "Witbank", "Secunda"],
    "North West": ["Rustenburg", "Potchefstroom", "Mahikeng"],
    "Northern Cape": ["Kimberley", "Upington"],
    "Outside South Africa": ["Gaborone", "Windhoek", "Maputo", "Harare", "London", "Dubai"],
}

# Marketing channels a school like this actually buys.
CAMPAIGN_CHANNELS = [
    ("Paid social", 26), ("Google Ads", 22), ("Organic search", 12), ("Email", 10),
    ("Referral", 8), ("Open day", 6), ("Career expo", 5), ("Webinar", 5),
    ("Radio", 3), ("Billboard", 2), ("Print", 1),
]

LEAD_SOURCES = [
    ("Web Enquiry Form", 30), ("Paid Social", 18), ("Google Ads", 16),
    ("Referral", 9), ("Open Day", 7), ("Career Expo", 5), ("Webinar", 5),
    ("Inbound Call", 5), ("Partner", 3), ("Walk-in", 2),
]

LEAD_STATUSES = [
    ("Open - Not Contacted", 22), ("Working - Contacted", 26), ("Nurture", 16),
    ("Qualified", 14), ("Converted", 14), ("Unqualified", 8),
]

OPPORTUNITY_STAGES = [
    ("Enquiry", 14), ("Qualification", 16), ("Application Sent", 16),
    ("Application Received", 14), ("Offer Made", 12),
    ("Closed Won", 16), ("Closed Lost", 12),
]

APPLICATION_STATUSES = [
    ("Submitted", 20), ("Under Review", 16), ("Accepted", 34),
    ("Declined", 12), ("Withdrawn", 10), ("Waitlisted", 8),
]

ENROLMENT_STATUSES = [
    ("Active", 54), ("Completed", 26), ("Withdrawn", 9),
    ("Deferred", 6), ("On Hold", 5),
]

RISK_BANDS = [("Low", 58), ("Medium", 27), ("High", 15)]

CAMPAIGN_THEMES = [
    "Digital Marketing Intake", "Design Thinking Push", "Brand Awareness",
    "Open Day Drive", "Bursary Awareness", "Career Switcher", "Matric Leavers",
    "Corporate Upskilling", "Alumni Referral", "UX Design Launch",
    "Copywriting Retarget", "Business School Awareness", "Summer School",
    "Data Analysis Intake", "Graphic Design Beginner", "Honours Applications",
]

RESPONSE_STATUSES = [("Sent", 44), ("Opened", 26), ("Clicked", 18), ("Responded", 12)]
