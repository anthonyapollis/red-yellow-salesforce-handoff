#!/usr/bin/env python3
"""Converts the ebook to PDF, updating the contents field on the way.

Word is used rather than a pure-Python converter for one specific reason: the
table of contents is a FIELD, not text. python-docx can insert the field but
cannot compute page numbers, so a converter that does not run Word produces a
PDF whose contents page is empty or says "update this field". Word updates the
field, then exports.

Falls back to LibreOffice if Word is not available - with a warning, because
that path does not reliably populate the field either.

    python export_pdf.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCX = REPO / "ebook" / "RedAndYellow_Data_Story.docx"
PDF = REPO / "ebook" / "RedAndYellow_Data_Story.pdf"

# wdExportFormatPDF, and update fields before export.
PS = r'''
$ErrorActionPreference = 'Stop'
$docx = '{docx}'
$pdf  = '{pdf}'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {{
    $doc = $word.Documents.Open($docx, $false, $true)   # confirm:false, readonly:true

    # Update every field, and the TOC specifically - a TOC will not populate
    # from Fields.Update() alone in some Word versions.
    $doc.Fields.Update() | Out-Null
    foreach ($toc in $doc.TablesOfContents) {{ $toc.Update() }}

    # Repaginate so the page numbers the TOC just wrote are the real ones.
    $doc.Repaginate()
    $doc.SaveAs([ref]$pdf, [ref]17)                     # 17 = wdFormatPDF
    Write-Output ("tocs: " + $doc.TablesOfContents.Count)
    $doc.Close([ref]0)
}} finally {{
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}}
'''


def via_word():
    script = PS.format(docx=str(DOCX), pdf=str(PDF))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[:800])
    return r.stdout.strip()


def via_libreoffice():
    for exe in [r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                "soffice"]:
        try:
            r = subprocess.run(
                [exe, "--headless", "--convert-to", "pdf", "--outdir",
                 str(PDF.parent), str(DOCX)],
                capture_output=True, text=True, timeout=900)
            if r.returncode == 0:
                return r.stdout.strip()
        except (FileNotFoundError, OSError):
            continue
    raise RuntimeError("LibreOffice not found either")


def main():
    if not DOCX.exists():
        raise SystemExit(f"build the ebook first: {DOCX}")
    if PDF.exists():
        PDF.unlink()

    try:
        info = via_word()
        engine = "Microsoft Word"
    except Exception as e:
        print(f"  Word conversion failed: {e}")
        print("  falling back to LibreOffice - the contents page may not "
              "populate on this path")
        info = via_libreoffice()
        engine = "LibreOffice"

    if not PDF.exists():
        raise SystemExit("conversion reported success but produced no PDF")

    # Read the page count back off the PDF rather than trusting Word's own
    # statistic - the two disagreed (28 vs 19), and the PDF is what ships.
    pages = "?"
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        rdr = PdfReader(str(PDF))
        pages = len(rdr.pages)
        toc_text = (rdr.pages[1].extract_text() or "") if pages > 1 else ""
        if "......" not in toc_text:
            print("  WARNING: the contents page does not look populated - "
                  "open the .docx and update the field manually")
    except ImportError:
        pass

    print(f"wrote {PDF}")
    print(f"  {PDF.stat().st_size / 1024:,.0f} KB   {pages} pages   via {engine}")
    if info:
        for line in info.splitlines():
            print(f"  {line}")


if __name__ == "__main__":
    main()
