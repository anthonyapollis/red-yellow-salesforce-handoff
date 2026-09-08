# Business rules
The ERD represents intended business rules. Scaffold lookup fields are optional for staged loads. The local validator checks this seed; implement relevant validation/uniqueness in the org before ongoing use.

- Programme: one exact displayed identity; confirm course-code equivalence before merging.
- Offering: one observed listing/variant; preserve duration value and unit.
- Intake: one dated start of an offering. Capacity is unknown.
- CampaignMember: exactly one LeadId or ContactId in this model; CampaignId required.
- Enquiry: exactly one Lead__c or Contact__c; offering required.
- Opportunity: one applicant and intake in this admissions model.
- Application: at most one per opportunity; contact and intake agree with opportunity.
- Student: one academic identity per contact; student number unique.
- Enrolment: at most one per application; student's contact matches applicant.
- Progress: unique enrolment/week, percentage values 0-100.

Every imported object has a unique external key. RY-DEMO keys are fictional. Local keys are not Salesforce record IDs.
Lead conversion is system-managed. The loader does not convert leads; use Salesforce conversion operations later if needed.
The one-applicant-per-opportunity model excludes corporate group deals; those need an opportunity-applicant junction.
Aggregate campaign spend separately to prevent multiplication across enrolments. Standard org stage and sample education-stage text are distinct. Actual revenue needs invoices/payments. Stage history is needed for time-in-stage reports.
