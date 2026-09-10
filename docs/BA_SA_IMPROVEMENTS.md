# BA and SA improvement assessment

**Scope:** Red & Yellow public website, CRM boundary, analytics warehouse, NiFi/Fabric integration and Power BI reporting.  
**Evidence:** read-only website crawl dated 10 September 2026, Salesforce reconciliation, ERD, dbt evidence and the current report model.

## What needs business analysis improvement

| Finding | Why it matters | BA improvement | Acceptance evidence |
|---|---|---|---|
| On-campus and online catalogue pages use different price availability and delivery labels. | Prospective students and reporting users can interpret the same course differently. | Define a catalogue data dictionary for programme, offering, delivery mode, fee, fee status, duration, intake and accreditation. Keep 'Enquire for price' as an explicit status. | Every catalogue row has one delivery mode, one fee status and a source URL/observed date. |
| The website has 126 sitemap URLs returning non-200, 169 missing descriptions and 435 missing canonicals. | Search traffic and application journeys can break before they reach CRM capture. | Prioritise a sitemap and metadata remediation backlog by traffic, programme value and application intent. | All indexable programme and application URLs return 200/approved redirects and pass the metadata contract. |
| Funnel terms are easy to read as counts rather than conversion stages. | Marketing, admissions and finance can make different decisions from the same dashboard. | Baseline definitions for lead, contact, opportunity, application, enrolment, agreed revenue, attribution and ROAS; record owner and refresh date. | KPI catalogue and reconciliation show the same denominator and date grain across Power BI, ebook and warehouse. |
| The modelled populations and live Base Edition Salesforce slice are different. | A reader could mistake synthetic custom-object rows for live CRM records. | Maintain a source-of-truth matrix: Salesforce operational slice, warehouse history, staged sample pack and model outputs. | Every published count names its system, object, filter and as-of date. |
| Recommendations need a decision owner and a feedback loop. | A score without an action is not an operating process. | Write user stories and acceptance criteria for marketing follow-up, admissions queues, student support and data-quality exceptions. | Each action has an owner, SLA, intervention record and outcome measure. |

## What needs systems analysis improvement

| Finding | Why it matters | SA improvement | Acceptance evidence |
|---|---|---|---|
| GA4 can arrive through the Data API or native BigQuery export. | The wrong route creates unnecessary cost or loses raw-event detail. | Specify two supported patterns: Data API -> NiFi -> OneLake for curated metrics; GA4 native export -> BigQuery -> Fabric for raw events. Keep them as separate source contracts. | Route decision, credential boundary, schema and reconciliation test are documented before activation. |
| Website, GA4, Salesforce and warehouse identifiers are not the same thing. | Joins can overstate campaign performance or expose user-level identifiers. | Use campaign/source/medium/date attribution keys first; keep CRM external IDs and analytics user identifiers in separate zones. | Duplicate, orphan and attribution-multiplication tests pass. |
| NiFi and Fabric failure states need operational visibility. | A green dashboard can hide a stalled or partially landed batch. | Add run ID, source watermark, row counts, reject counts, retry state, quarantine path and alert owner to each ingestion contract. | A failed-run test produces an alert and a replayable parked batch without duplicate rows. |
| The SEO audit found 435 pages without JSON-LD and 310 images without alt text. | These are repeatable template defects, not one-off page edits. | Implement page-template controls for title, description, canonical, H1, OG/Twitter, BreadcrumbList and image alt text. | CI or scheduled crawl reports coverage by template and blocks release below the agreed threshold. |
| Power BI currently needs explicit empty-state and slicer rules. | Blank-only filters look like missing data and mislead users. | Define allowed slicers, null labels, sort order, accessible contrast, text-size minimums and tooltip definitions in the report specification. | No slicer offers only '(Blank)'; visual layout validation and a screenshot review pass. |
| ML outputs are decision support, not automatic decisions. | A dropout score can create unfair or unexplained interventions. | Document feature cutoff, cohort, model version, calibration, drift checks, human review and appeal path. | Model card, monthly lift/drift review and logged intervention outcomes exist before operational use. |

## Website-to-CRM-to-Fabric traceability

1. A visitor lands on a programme or application page; GA4 records consented campaign and page events.
2. A form submission creates or updates a Salesforce Lead/Contact using the external ID and duplicate rules.
3. Admissions qualification creates an Opportunity; the warehouse reconciles stage, campaign and date keys.
4. Applications and enrolments remain warehouse entities while the Base Edition org cannot host the proposed custom objects.
5. Power BI reports acquisition, funnel, course demand, learner risk and data quality from tested marts.
6. The SEO crawl, CRM reconciliation and pipeline run logs provide release evidence and a feedback loop.

## BA/SA priority backlog

- **Now:** fix non-200 sitemap entries; publish the catalogue/KPI/source-of-truth dictionaries; remove blank-only slicers; finish Fabric SQL compatibility work.
- **Next:** add metadata and structured-data template controls; activate the chosen GA4 route; add ingestion observability and a replay test.
- **Then:** connect website campaign events to CRM attribution; pilot course-risk interventions with human review; measure SEO-to-enquiry and enquiry-to-enrolment lift.
- **Governance:** review definitions, model drift, data quality and intervention outcomes monthly; keep synthetic demonstration data labelled in every deliverable.

These recommendations describe improvements identified from the analysed website and the implemented platform. They are a delivery backlog, not a claim that website or production CRM changes have already been made.
