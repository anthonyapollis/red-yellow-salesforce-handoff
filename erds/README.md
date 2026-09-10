# Diagram versions
03_salesforce_canonical.mmd is the current implementation target.
01_original_conceptual_ARCHIVE.mmd and 02_catalogue_revision_ARCHIVE.mmd preserve earlier designs.
04_analytics_pipeline.mmd is the earlier integration flow, not an ERD.
Open index.html for diagrams (rendering requires internet), or use .mmd files in a Mermaid editor. Raw source remains available offline.
The ebook-ready overview image is generated offline with python erds/render_canonical_erd.py; it keeps the three domains in separate lanes and includes the full relationship registry.
Archived versions must not be independently deployed as extra objects. ERD cardinalities are intended business rules; optional Salesforce lookup metadata does not enforce all of them. See docs/BUSINESS_RULES.md.
