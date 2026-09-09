#!/usr/bin/env python3
"""Exports what is in Salesforce right now to Excel and CSV, with record links.

Reads the org through the API rather than reading the files that were sent to
it, so the export shows what Salesforce actually holds - including anything the
org changed on the way in.

Every row carries a clickable Lightning URL, so a number in the workbook can be
opened in the CRM without searching for it.

    python export_salesforce_data.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "salesforce"))
from sf_auth import resolve  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "reporting" / "salesforce_export"
XLSX = REPO / "reporting" / "Salesforce_Imported_Data.xlsx"
API = "62.0"

OBJECTS = {
    "Account": ["Id", "Name", "RY_External_ID__c", "CreatedDate"],
    "Contact": ["Id", "FirstName", "LastName", "Email", "AccountId",
                "RY_External_ID__c", "CreatedDate"],
    "Lead": ["Id", "FirstName", "LastName", "Company", "Email", "Status",
             "RY_External_ID__c", "RY_Sample_Status__c", "CreatedDate"],
    "Opportunity": ["Id", "Name", "StageName", "CloseDate", "AccountId",
                    "RY_External_ID__c", "RY_Sample_Stage__c",
                    "RY_Expected_Value_ZAR__c", "CreatedDate"],
}

RED, CHARCOAL, SLATE, RULE = "#E03127", "#22252A", "#5A6472", "#D8DDE4"


def main():
    url, tok = resolve()
    H = {"Authorization": f"Bearer {tok}"}
    # my.salesforce.com is the API host; lightning.force.com is the UI host.
    ui = url.replace(".my.salesforce.com", ".lightning.force.com")

    def soql(q):
        path = "/services/data/v" + API + "/query?q=" + urllib.parse.quote(q)
        rows = []
        while True:
            req = urllib.request.Request(
                path if path.startswith("http") else url + path, headers=H)
            d = json.load(urllib.request.urlopen(req, timeout=180))
            rows.extend(d["records"])
            if d.get("done") or not d.get("nextRecordsUrl"):
                return rows
            path = d["nextRecordsUrl"]

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"reading {url}\n")

    frames = {}
    for obj, fields in OBJECTS.items():
        rows = soql(f"SELECT {','.join(fields)} FROM {obj} "
                    f"WHERE RY_External_ID__c != null ORDER BY RY_External_ID__c")
        df = pd.DataFrame([{k: r.get(k) for k in fields} for r in rows])
        if df.empty:
            print(f"  {obj:<14}{0:>7} rows")
            continue
        df.insert(1, "Salesforce_Link",
                  [f"{ui}/lightning/r/{obj}/{i}/view" for i in df["Id"]])
        df.to_csv(OUT / f"{obj}.csv", index=False)
        frames[obj] = df
        print(f"  {obj:<14}{len(df):>7} rows")

    if not frames:
        raise SystemExit("nothing tagged with RY_External_ID__c found in the org")

    with pd.ExcelWriter(XLSX, engine="xlsxwriter") as xw:
        wb = xw.book
        hdr = wb.add_format({"bold": True, "font_color": "#FFFFFF",
                             "bg_color": CHARCOAL, "border": 1,
                             "border_color": CHARCOAL, "valign": "vcenter"})
        cell = wb.add_format({"border": 1, "border_color": RULE})
        link = wb.add_format({"font_color": "#1B6EC2", "underline": 1,
                              "border": 1, "border_color": RULE})
        title = wb.add_format({"bold": True, "font_size": 15,
                               "font_color": CHARCOAL})
        sub = wb.add_format({"font_color": SLATE, "font_size": 10})

        # Contents sheet, with list-view links per object.
        ws = wb.add_worksheet("Contents")
        ws.hide_gridlines(2)
        ws.set_column("A:A", 2)
        ws.set_column("B:B", 26)
        ws.set_column("C:C", 14)
        ws.set_column("D:D", 76)
        ws.write("B2", "Data imported into Salesforce", title)
        ws.write("B3", f"{url}   ·   exported {datetime.now():%d %B %Y %H:%M}", sub)
        ws.write("B5", "All records are tagged with RY_External_ID__c. "
                       "Nothing else in the org was touched.", sub)
        ws.write_row("B7", ["Object", "Records", "Open the list view in Salesforce"],
                     hdr)
        r = 7
        for obj, df in frames.items():
            r += 1
            ws.write(r, 1, obj, cell)
            ws.write_number(r, 2, len(df), cell)
            ws.write_url(r, 3, f"{ui}/lightning/o/{obj}/list",
                         link, f"{ui}/lightning/o/{obj}/list")
        r += 3
        ws.write(r, 1, "每 row on the object sheets carries a direct record link."
                 .replace("每", "Every"), sub)

        for obj, df in frames.items():
            df.to_excel(xw, sheet_name=obj, index=False, startrow=1, header=False)
            sh = xw.sheets[obj]
            for j, name in enumerate(df.columns):
                sh.write(0, j, name, hdr)
                width = {"Salesforce_Link": 62, "Id": 20, "Email": 34,
                         "Name": 34, "RY_External_ID__c": 22}.get(name, 16)
                sh.set_column(j, j, width, link if name == "Salesforce_Link" else cell)
            sh.freeze_panes(1, 0)
            sh.autofilter(0, 0, len(df), len(df.columns) - 1)

    total = sum(len(d) for d in frames.values())
    print(f"\n  {total:,} records")
    print(f"  workbook  {XLSX}")
    print(f"  csv       {OUT}")
    print(f"\n  Salesforce list views:")
    for obj in frames:
        print(f"    {obj:<14}{ui}/lightning/o/{obj}/list")


if __name__ == "__main__":
    main()
