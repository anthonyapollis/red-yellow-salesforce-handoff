# dbt evidence and reproducibility

Latest local run: 2026-09-10T12:55:22.501194Z
dbt version: 1.11.12
Target: duckdb (the validated local transformation runtime).

## Verified run

dbt build completed with 87 nodes: 36 models and 51 tests.
Status counts: pass=51, success=36.
Elapsed time recorded by dbt: 383.6 seconds.

The generated screenshot ev_06_dbt_tests.png is rendered directly from target/run_results.json; it is evidence of this run, not a hand-drawn claim.
The medallion and relationship figures ev_09_medallion.png and ev_10_data_model.png are read from the dbt manifest.

## Delivery-mode check

The curated offering dimension contains 15 On-campus offerings and 74 Off-campus offerings.
The source field Catalogue_Section__c remains Online education for online listings; Delivery_Mode__c is mapped to Off-campus for analytics.

## Reproduce

    Set-Location dbt_redandyellow
    $env:DBT_PROFILES_DIR='.'
    dbt build
    dbt docs generate
    Set-Location ..
    python reporting/capture_evidence.py
    python reporting/build_ebook.py
    python reporting/export_pdf.py

## Scope and limitation

This evidence is for the local DuckDB target. Fabric connectivity and bronze access were verified separately, but the Fabric silver/gold build still has documented T-SQL compatibility work outstanding. Do not describe this local run as proof that the Fabric target is deployed.
