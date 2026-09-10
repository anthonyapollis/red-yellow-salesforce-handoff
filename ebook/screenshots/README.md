# Real UI evidence for the e-book

`reporting/build_ebook.py` appends every PNG or JPG in this folder to the
**Screens from the org** section. The leading number fixes the reading order;
underscores become the caption. Keep the browser or desktop chrome visible only
when it helps establish provenance. Blur or crop personal data, tokens, IDs,
and connection strings before adding a capture.

Use these filenames for the outstanding evidence:

1. `01_NiFi_flow_canvas.png` — the running Red & Yellow process group, its
   input/output ports, and the Salesforce-to-bronze flow.
2. `02_Fabric_warehouse_and_lakehouse.png` — `WS_RedAndYellow`, the lakehouse
   bronze area, and the populated Warehouse objects.
3. `03_Canonical_ERD.png` — the current canonical model, based on
   `erds/03_salesforce_canonical.mmd`; do not capture an archived revision.
4. `04_PowerBI_executive_summary.png` — the refreshed Executive Summary after
   the dataset has been refreshed; do not save the PBIP from Desktop.

The generated architecture, terminal evidence, and model diagrams remain in
`ebook/figures/`. These real captures complement that evidence; they do not
replace it.