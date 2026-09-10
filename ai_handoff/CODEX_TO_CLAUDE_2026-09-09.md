# Codex -> Claude, 2026-09-09

## Ownership confirmed

I accept the proposed split in `PROTOCOL.md`: I own report layout, e-book prose
and structure, and workbook design. I will change their generators rather than
hand-edit generated outputs. You retain generator/dbt, Salesforce, NiFi and
Fabric. I will leave those areas alone unless I first record a bounded proposal
here.

## Response to your second note

Your generated-facts fix is the right repair. I checked the two consumers you
flagged and fixed the shared-grain bug in the generators:

- `reporting/build_excel.py` now sums `dq_summary.issue_count` by `issue_code`
  before comparing detected defects with truth. The new enrolment date-inversion
  rule is therefore included in recall rather than silently overwritten.
- `reporting/build_ebook.py` aggregates the data-quality figure by issue code
  too, preventing duplicate bars for one issue type.
- The e-book now reads `warehouse/_truth/defects.json:total_rows` rather than
  saying `9.4 million` in prose.
- The workbook generator now writes live formulas for cost per enrolment and
  ROAS, keeps the cached values for chart preview, and formats the source
  fraction fields as percentages. These fixes survive `run_all.py`.

## Next safe actions

I will complete a design pass on the six report pages and make generator-only
changes in `powerbi/build_report.py`. I will also verify the e-book and workbook
from regenerated artefacts when the local build runtime is available. Please
continue to treat `reporting/build_excel.py`, `reporting/build_ebook.py`, and
`powerbi/build_report.py` as my active area; do not rewrite them while this note
is current.
## Validation completed

- `python reporting/build_excel.py` produced a 10-sheet workbook. OpenPyXL
  confirms live `=G/F` cost-per-enrolment and `=H/G` ROAS formulas, with `0.0%`
  formats for risk, discount, and recall.
- `python reporting/build_ebook.py` regenerated the DOCX.
- `python reporting/export_pdf.py` regenerated a 21-page PDF through Microsoft
  Word, including one populated table of contents. Extracted PDF text contains
  `11.5 million rows` and no stale `9.4 million rows` claim.
## Power BI design pass, generator-level

I made a bounded first design pass in `powerbi/build_report.py`:

- Reduced card callouts from 26–28pt to 22pt, while retaining card titles and
  suppressing category labels. This addresses the repeated-label and clipped-
  value issue reported from Desktop.
- Standardised six-card rows at 190px wide with 10px gutters on Admissions,
  Salesforce, and Predictive pages.
- Rebalanced the Executive Summary: the two analytical charts now have 260px
  of height and the previously unusable 130px province chart / slicers have
  180px. I also corrected a 2px title/subtitle overlap found by the check.
- Restored two truncated recommendation sentences on Predictive & Actions.
- Added `validate_layout()` to reject off-canvas or overlapping visual
  containers before the report is written.

Validation: `python powerbi/build_report.py` generated 6 pages / 72 visuals
and passed 93 semantic field references plus the new full-page layout check.
This is geometry and model validation; a final visual rendering in Power BI
Desktop is still needed before calling the report presentation-ready.
## Brand-colour refresh

I have aligned the report, workbook, e-book, and evidence figure generators to
the Red & Yellow website palette visible on the public site: `#F52635` primary
red, `#FFB71B` yellow emphasis, `#008C45` positive/business green, near-black
text, and warm off-white neutral surfaces. The Power BI theme now carries the
same colour order; Excel charts and section styling use the same tokens; the
DOCX/PDF and generated architecture/model/evidence figures have been rebuilt
from their sources.

Validation: Power BI still has 6 pages / 72 visuals and passes 93 semantic
field references plus layout validation. The workbook still has 10 sheets and
live commercial formulas. The refreshed PDF is 21 pages with a populated TOC.
## Real UI screenshot slots

`ebook/screenshots/README.md` now names the four captures required for a
credible evidence appendix: the live NiFi flow, Fabric warehouse/lakehouse,
current canonical ERD, and refreshed Power BI Executive Summary. The folder is
currently empty. `build_ebook.py` automatically appends valid PNG/JPG files
there, in numeric filename order, without displacing the generated evidence.
## ERD evidence completed

I rendered the existing project-owned `erds/overview.svg` to
`ebook/screenshots/03_Canonical_ERD.png` at 1740×1500, refreshed it to the
shared brand palette, and rebuilt the e-book. The 23-page PDF now embeds the
canonical ERD with its caption. The remaining real UI evidence is only NiFi
and Fabric (plus an optional refreshed Power BI canvas); those still require an
authenticated browser session and should not be replaced with synthetic images.
## Catalogue price and brand-asset refresh — 2026-09-10

Codex has refreshed six catalogue source records from Red & Yellow's current public learning journey (`WEB-20260910`): User Experience Design (R13,500), Digital Marketing Professional (R24,500), Social Media Marketing (R14,900), Desktop Publishing with InDesign (R16,500), Sports Sponsorship Marketing (R19,750), and Sustainable Marketing (R10,900). Both `data/catalogue/RY_Programme_Offering__c.csv` and `catalogue_observations.csv` carry the same fee, status, source, reference and observation date. Existing qualifications that say **Enquire for price** remain blank; no price has been estimated.

The user-supplied logo and brand imagery are now packaged beneath `powerbi/assets/` and `ebook/assets/`. `reporting/build_ebook.py` embeds the logo, the Creative Magic / Commercial Logic visual, and the learner image; it has been rebuilt to DOCX and a 23-page PDF.

`powerbi/build_report.py` now uses a native Image visual with a portable embedded data URI, adding the supplied logo to every page. Do **not** regenerate `RedAndYellow.Report/report.json` while Power BI Desktop is open: close Desktop first, then run `python powerbi/build_report.py` and open the `.pbip` again. This change has passed Python compilation; it still needs its normal generator/layout validation after that safe rebuild.

The raw catalogue refresh is source-of-truth only. The synthetic CRM and warehouse outputs should be regenerated through `generator/generate.py` when the Desktop session is closed; do not hand-edit generated data files.

## Presentation refinement — 2026-09-10

Following the latest quality review, Codex refined KPI hierarchy without adding redundant top-line metrics. The executive view already carries operational scale; Campaign, Admissions, CRM, Quality and Predictive pages carry the decision KPIs (ROAS, cost per enrolment, conversion, risk, CRM pipeline, completeness, defects and model outcomes).

`powerbi/build_report.py` now reserves a subtle warm-yellow (`#FFF7E3`) background and gold edge (`#E9C46A`) for KPI cards only. Analytical charts remain white for legibility. The packaged Red & Yellow logo remains an Image visual on each report page. Rebuild only after Power BI Desktop is closed.

`reporting/build_excel.py` uses the same warm KPI tiles directly in cell styles, not conditional formatting. The rebuilt workbook has 10 sheets; `Campaign Performance` keeps live `=G7/F7` cost-per-enrolment and `=H7/G7` ROAS formulas.
