# Red & Yellow diagrams

Canonical version: 03. Archived designs are context only.

## 01_original_conceptual_ARCHIVE

```mermaid
erDiagram
    CAMPAIGN ||--o{ CAMPAIGN_MEMBER : includes
    LEAD o|--o{ CAMPAIGN_MEMBER : participates
    CONTACT o|--o{ CAMPAIGN_MEMBER : participates
    CONTACT o|--o{ LEAD : converted_into
    CONTACT ||--o{ OPPORTUNITY : applicant_for
    CAMPAIGN o|--o{ OPPORTUNITY : primary_source
    OPPORTUNITY ||--o| APPLICATION : produces
    PROGRAMME ||--o{ INTAKE : offers
    INTAKE ||--o{ APPLICATION : receives
    CONTACT ||--o| STUDENT : becomes
    STUDENT ||--o{ ENROLMENT : has
    APPLICATION ||--o| ENROLMENT : results_in
    ENROLMENT ||--o{ STUDENT_PROGRESS : tracks
    CAMPAIGN {
        string campaign_id PK
        string campaign_name
        string channel
        date start_date
        decimal spend_zar
    }
    LEAD {
        string lead_id PK
        string full_name
        string email
        string lead_source
        string status
        datetime created_at
        string converted_contact_id FK
    }
    CAMPAIGN_MEMBER {
        string campaign_member_id PK
        string campaign_id FK
        string lead_id FK
        string contact_id FK
        string response_status
        datetime first_responded_at
    }
    CONTACT {
        string contact_id PK
        string full_name
        string email
        string phone
    }
    OPPORTUNITY {
        string opportunity_id PK
        string applicant_contact_id FK
        string primary_campaign_id FK
        string stage
        decimal expected_value_zar
        date expected_close_date
    }
    PROGRAMME {
        string programme_id PK
        string programme_name
        string qualification_type
        int duration_weeks
    }
    INTAKE {
        string intake_id PK
        string programme_id FK
        date start_date
        string delivery_mode
        int capacity
    }
    APPLICATION {
        string application_id PK
        string opportunity_id FK
        string intake_id FK
        date submitted_date
        string status
        date decision_date
    }
    STUDENT {
        string student_id PK
        string contact_id FK
        string student_number UK
    }
    ENROLMENT {
        string enrolment_id PK
        string student_id FK
        string application_id FK
        date enrolled_date
        string status
        decimal agreed_fee_zar
    }
    STUDENT_PROGRESS {
        string progress_id PK
        string enrolment_id FK
        date week_start
        decimal attendance_pct
        decimal assessment_average_pct
        int overdue_assignments
        string risk_band
    }
```


## 02_catalogue_revision_ARCHIVE

```mermaid
erDiagram
    PROGRAMME ||--o{ PROGRAMME_OFFERING : available_as
    PROGRAMME_OFFERING ||--o{ INTAKE : scheduled_for
    CONTACT ||--o{ PROGRAMME_ENQUIRY : makes
    PROGRAMME_OFFERING ||--o{ PROGRAMME_ENQUIRY : receives
    CONTACT ||--o{ APPLICATION : submits
    INTAKE ||--o{ APPLICATION : receives
    APPLICATION ||--o| ENROLMENT : becomes
    PROGRAMME {
        string programme_id PK
        string programme_name
        string qualification_type
        string listed_awarding_or_quality_body
    }
    PROGRAMME_OFFERING {
        string offering_id PK
        string programme_id FK
        string delivery_mode
        string study_pace
        int duration_value
        string duration_unit
        string source_url
    }
    INTAKE {
        string intake_id PK
        string offering_id FK
        date start_date
        decimal advertised_fee
        string currency
        string price_status
        datetime observed_at
    }
    CONTACT {
        string contact_id PK
        string salesforce_contact_id UK
        string full_name
        string email
    }
    PROGRAMME_ENQUIRY {
        string enquiry_id PK
        string contact_id FK
        string offering_id FK
        datetime enquiry_date
        string channel
        string status
    }
    APPLICATION {
        string application_id PK
        string contact_id FK
        string intake_id FK
        string salesforce_opportunity_id
        date application_date
        string status
    }
    ENROLMENT {
        string enrolment_id PK
        string application_id FK
        string student_id FK
        date enrolment_date
        decimal agreed_fee
        string status
    }
```


## 03_salesforce_canonical

```mermaid
erDiagram
    RY_Programme__c ||--o{ RY_Programme_Offering__c : has
    RY_Programme_Offering__c ||--o{ RY_Intake__c : schedules
    Account o|--o{ Contact : groups
    Account o|--o{ Opportunity : sponsors
    Campaign ||--o{ CampaignMember : includes
    Lead o|--o{ CampaignMember : participates
    Contact o|--o{ CampaignMember : participates
    Contact o|--o{ Lead : converted_into
    Contact ||--o{ Opportunity : applicant
    Campaign o|--o{ Opportunity : primary_source
    RY_Intake__c ||--o{ Opportunity : target
    Contact o|--o{ RY_Programme_Enquiry__c : enquires
    Lead o|--o{ RY_Programme_Enquiry__c : enquires
    RY_Programme_Offering__c ||--o{ RY_Programme_Enquiry__c : attracts
    Contact ||--o{ RY_Application__c : submits
    RY_Intake__c ||--o{ RY_Application__c : receives
    Opportunity ||--o| RY_Application__c : produces
    Contact ||--o| RY_Student__c : becomes
    RY_Student__c ||--o{ RY_Enrolment__c : has
    RY_Application__c ||--o| RY_Enrolment__c : becomes
    RY_Enrolment__c ||--o{ RY_Student_Progress__c : tracks
    RY_Programme__c {
        id Id PK
        string RY_External_ID__c UK
        string Title__c
        string Category__c
        string Credential_Text__c
        string Listed_Body__c
    }
    RY_Programme_Offering__c {
        id Id PK
        string RY_External_ID__c UK
        id Programme__c FK
        string Title__c
        string Catalogue_Section__c
        string Delivery_Mode__c
        string Study_Pace__c
        int Duration_Value__c
        string Duration_Unit__c
        decimal Advertised_Fee_ZAR__c
        string Price_Status__c
        string Source_URL__c
        string Source_Refs__c
        date Observed_Date__c
        string Notes__c
    }
    RY_Intake__c {
        id Id PK
        string RY_External_ID__c UK
        id Offering__c FK
        date Start_Date__c
    }
    Account {
        id Id PK
        string Name
        string RY_External_ID__c UK
    }
    Contact {
        id Id PK
        string FirstName
        string LastName
        string Email
        id AccountId FK
        string RY_External_ID__c UK
    }
    Lead {
        id Id PK
        string FirstName
        string LastName
        string Email
        string Company
        string Status
        id ConvertedContactId FK
        string RY_External_ID__c UK
        string RY_Sample_Status__c
    }
    Campaign {
        id Id PK
        string Name
        date StartDate
        boolean IsActive
        string RY_External_ID__c UK
        string RY_Channel__c
        decimal RY_Spend_ZAR__c
    }
    CampaignMember {
        id Id PK
        id CampaignId FK
        id ContactId FK
        id LeadId FK
        string RY_External_ID__c UK
    }
    Opportunity {
        id Id PK
        string Name
        string StageName
        date CloseDate
        id AccountId FK
        id CampaignId FK
        string RY_External_ID__c UK
        id RY_Applicant__c FK
        id RY_Intake__c FK
        string RY_Sample_Stage__c
        decimal RY_Expected_Value_ZAR__c
    }
    RY_Programme_Enquiry__c {
        id Id PK
        string RY_External_ID__c UK
        id Contact__c FK
        id Lead__c FK
        id Offering__c FK
        date Enquiry_Date__c
        string Channel__c
        string Status__c
    }
    RY_Application__c {
        id Id PK
        string RY_External_ID__c UK
        id Contact__c FK
        id Intake__c FK
        id Opportunity__c FK
        date Submitted_Date__c
        string Status__c
        date Decision_Date__c
    }
    RY_Student__c {
        id Id PK
        string RY_External_ID__c UK
        id Contact__c FK
        string Student_Number__c
    }
    RY_Enrolment__c {
        id Id PK
        string RY_External_ID__c UK
        id Student__c FK
        id Application__c FK
        date Enrolled_Date__c
        string Status__c
        decimal Agreed_Fee_ZAR__c
    }
    RY_Student_Progress__c {
        id Id PK
        string RY_External_ID__c UK
        id Enrolment__c FK
        date Week_Start__c
        decimal Attendance_Pct__c
        decimal Assessment_Average_Pct__c
        int Overdue_Assignments__c
        string Risk_Band__c
    }
```


## 04_analytics_pipeline

```mermaid
flowchart LR
    A["Salesforce: Leads, Contacts, Campaigns, Opportunities"] --> B["Apache NiFi: Extract and load"]
    B --> C[("Database: raw Salesforce tables")]
    C --> D["dbt: clean, join and test"]
    E["Student and academic systems"] --> B
    D --> F[("Reporting tables")]
    F --> G["Power BI"]
```
