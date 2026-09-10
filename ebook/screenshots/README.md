# UI screenshots for the ebook

`reporting/build_ebook.py` embeds every image in this folder automatically and
captions it from the filename: `04_Fabric_workspace.png` becomes "Fabric
workspace". Drop a file in, re-run the ebook build, done.

```bash
python reporting/build_ebook.py
python reporting/export_pdf.py
```

Number the files so they land in the intended order.

## What is here

| File | State |
|---|---|
| `03_Canonical_ERD.png` | **Done.** Rendered from `erds/overview.svg`, brand palette. |
| `04_Fabric_workspace.png` | **Outstanding.** |
| `05_NiFi_flow_canvas.png` | **Outstanding.** |

## Why the last two are outstanding

Both sit behind an authenticated browser session. Claude is not permitted to
type passwords into login forms, so it can open the page and see it but cannot
sign in. That is the whole blocker — nothing technical.

**Both pages have been opened and confirmed reachable:**

- **Fabric** — `app.fabric.microsoft.com` → workspace `WS_RedAndYellow`. Already
  signed in; the workspace listing renders showing `LH_RedAndYellow`
  (Lakehouse), its SQL analytics endpoint, and `WH_RedAndYellow` (Warehouse).
  Capture that listing. Worth also capturing the Lakehouse's `Files/bronze`
  showing the 13 parquet folders.
- **NiFi** — `https://localhost:8443/nifi`. NiFi is **not running by default**;
  start it first and give it 6–8 minutes:

  ```
  C:\Apache\nifi-2.9.0-bin\nifi-2.9.0\bin\nifi.cmd start
  ```

  Log in with the credentials in `C:\Apache\NIFI_LOGIN.txt` (deliberately kept
  outside this repo), then open the `RY_Salesforce_to_Fabric` process group and
  capture the canvas with the stage groups visible.

Windows: `Win+Shift+S` captures a region straight to the clipboard, then paste
into Paint and save here under the filename above.

## Do not substitute rendered figures for these

`reporting/capture_infra.py` draws NiFi and Fabric state read live from their
APIs. Those are genuine evidence and they belong in the ebook, but they are
**not** UI screenshots and Anthony has repeatedly rejected them as a stand-in.
If you cannot authenticate, say so rather than filling the gap with a render.
