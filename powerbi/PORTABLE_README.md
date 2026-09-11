# Portable Power BI project

Open `powerbi/RedAndYellow.pbip` with Power BI Desktop PBIP support. Keep the sibling folders `RedAndYellow.Report`, `RedAndYellow.SemanticModel`, `data` and `assets` together.

The semantic model reads the included `powerbi/data/*.parquet` files with project-relative paths, so it does not depend on the creator's Windows profile. Power BI cache and local editor state are intentionally excluded. Refreshing Salesforce, Microsoft Fabric, GA4, BigQuery, Campaign Manager 360 or DV360 sources requires credentials and connector configuration in the destination environment.
