# DIRTY-DATA EXERCISE UPDATE
Original reference assumptions/rules follow below. The user now requires deliberately dirty data: default imports use data/dirty_loadable. Semantic rules below are intentionally violated in selected records; treat them as profiling checks, not automatic cleaning instructions. See DIRTY_DATA_GUIDE.md and ISSUE_REGISTER.csv. Original source observations remain unchanged.

# Provenance and assumptions
89 distinct visible listings were transcribed across 17 screenshots. Repeated cards are consolidated. sources/screenshots.csv indexes every image; Source_Refs__c links offerings to images. Partial cards with visible titles are included, with unseen details blank. This is not claimed to be the complete live catalogue.

## Identity
83 exact displayed titles are conservative programme identities. Exact same names across page sections share a programme but have separate offerings. Confirm official qualification codes before treating this as verified equivalence.
Part-Time titles remain separate programme identities pending confirmation. BBA "in" versus colon title variants are deliberately not auto-merged. Earlier proposed merges are candidates, not performed here.

## Delivery and classification
On-campus listings have proposed On-campus delivery.
Online-ed listings have Catalogue_Section__c = Online education and Delivery_Mode__c = Unconfirmed: a page section alone does not establish actual delivery.
Study pace is Part-time only when the title says so, otherwise Not stated.
Category__c is a proposed title/context classification, not an official accreditation category. CHE/QCTO/SETA labels are preserved as listed source text, not asserted to be awarding bodies.
Micro-course credential text is blank when not visible.

## Fees, durations and dates
Amounts are displayed ZAR. No VAT, annual/total fee or discount assumption is made.
Observed fees live on offerings so undated micro courses can retain their prices. Intake records exist only for visible start dates.
Enquire -> blank amount + Enquire status. Unseen/clipped prices -> blank + Not shown.
Agreed student fee is separate from advertised price.
Money uses Number(18,2) fields explicitly named ZAR to avoid inheriting an unknown org currency. Standard Opportunity.Amount and Campaign.ActualCost are not populated.
Observed_Date__c = 2026-09-08 is screenshot context, not website modification time.

## Specific uncertainties retained
- Part-Time Higher Certificate in Graphic Design says 1 year; retained as shown.
- User Experience Design, Digital Marketing Professional, Social Media Marketing, Desktop Publishing with InDesign, Sports Sponsorship Marketing and Sustainable Marketing have clipped/unseen prices.
- Online Project Manager, Part-Time Advanced Diploma in User Centered Design and Bachelor of Commerce in Marketing have clipped prices.
- Last online Honours and BBA cards have clipped duration/body/price; not copied from campus versions.
- Missing micro-course dates do not mean self-paced.
- A catalogue listing is not a Salesforce Campaign or Opportunity.

## Fictional records
All people use example.com. Account, campaign spend, pipeline stages, applications, fees, student IDs and progress are synthetic. September/October progress is a future scenario relative to capture, not observed performance.
The first July/12-week Digital Marketing example is archived only; it does not overwrite the actual displayed 10-week Digital Marketing course.
