#!/usr/bin/env python3
"""Deploys salesforce/force-app to an org using the Metadata REST API.

Why this exists: the Salesforce CLI is not installed on this machine and needs
Node, but the org has no RY_* objects, so the data import cannot run until the
metadata lands. The Metadata API is reachable over plain REST with an access
token, so no CLI is required.

The one real piece of work is format conversion. force-app is in SFDX *source*
format, which splits every field into its own file under objects/<Obj>/fields/.
The Metadata API wants *metadata* format: one .object file per object with the
fields nested inside it. This script does that merge, writes package.xml, zips
it, deploys, and polls until the deployment finishes.

    python deploy_metadata.py --check-only     # validate against the org, no changes
    python deploy_metadata.py                  # deploy for real
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf_auth import resolve  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "salesforce" / "force-app" / "main" / "default"
API = "62.0"
NS = "http://soap.sforce.com/2006/04/metadata"

BOUNDARY = "----RYDeployBoundary7f3a"


def inner(xml: str, tag: str) -> str:
    """Return the contents of the single root element, minus the XML prolog."""
    m = re.search(rf"<{tag}[^>]*>(.*)</{tag}>", xml, re.S)
    if not m:
        raise SystemExit(f"could not parse a <{tag}> element")
    return m.group(1)


def build_object(obj_dir: Path, standard_only: bool = False) -> str:
    """Merge one source-format object directory into a metadata-format .object."""
    parts = []
    meta = obj_dir / f"{obj_dir.name}.object-meta.xml"
    if meta.exists():
        parts.append(inner(meta.read_text(encoding="utf-8"), "CustomObject"))

    for f in sorted((obj_dir / "fields").glob("*.field-meta.xml")):
        body = f.read_text(encoding="utf-8")
        # A lookup to an object we are not deploying cannot resolve.
        if standard_only:
            ref = re.search(r"<referenceTo>([^<]+)</referenceTo>", body)
            if ref and ref.group(1).endswith("__c"):
                continue
        parts.append("<fields>" + inner(body, "CustomField") + "</fields>")

    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<CustomObject xmlns="{NS}">' + "".join(parts) + "</CustomObject>")


def build_package(standard_only=False):
    """Return (zip_bytes, manifest) for everything under force-app.

    standard_only drops the custom objects and any field that looks them up.
    Salesforce Base Edition (Starter Suite) permits zero custom objects, so on
    such an org the only deployable part of this model is the custom fields on
    standard objects.
    """
    objects, permsets, skipped = [], [], []
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in sorted((SRC / "objects").iterdir()):
            if not d.is_dir():
                continue
            if standard_only and d.name.endswith("__c"):
                skipped.append(d.name)
                continue
            xml = build_object(d, standard_only=standard_only)
            objects.append(d.name)
            z.writestr(f"objects/{d.name}.object", xml)

        ps_dir = SRC / "permissionsets"
        if ps_dir.exists() and not standard_only:
            for f in sorted(ps_dir.glob("*.permissionset-meta.xml")):
                name = f.name.replace(".permissionset-meta.xml", "")
                permsets.append(name)
                body = f.read_text(encoding="utf-8")
                if not body.lstrip().startswith("<?xml"):
                    body = '<?xml version="1.0" encoding="UTF-8"?>\n' + body
                z.writestr(f"permissionsets/{name}.permissionSet", body)

        types = ""
        for members, name in ((objects, "CustomObject"), (permsets, "PermissionSet")):
            if members:
                types += "<types>" + "".join(f"<members>{m}</members>" for m in members)
                types += f"<name>{name}</name></types>"
        z.writestr("package.xml",
                   f'<?xml version="1.0" encoding="UTF-8"?>\n<Package xmlns="{NS}">'
                   f"{types}<version>{API}</version></Package>")

    return buf.getvalue(), {"objects": objects, "permissionSets": permsets,
                            "skipped": skipped}


def post_deploy(url, token, zip_bytes, check_only, test_level=None):
    """POST the zip as multipart/form-data to the Metadata deployRequest resource.

    testLevel is deliberately omitted by default. A Salesforce trial org counts
    as a *production* org, and production rejects NoTestRun outright with
    INVALID_OPERATION. This package contains no Apex, so letting Salesforce pick
    the level is both valid and correct; pass --test-level RunLocalTests if an
    org's settings demand an explicit one.
    """
    deploy_options = {
        "checkOnly": check_only,
        "singlePackage": True,
        "rollbackOnError": True,
        "ignoreWarnings": False,
    }
    if test_level:
        deploy_options["testLevel"] = test_level
    opts = {"deployOptions": deploy_options}

    parts = []
    parts.append(
        f"--{BOUNDARY}\r\n"
        'Content-Disposition: form-data; name="json"\r\n'
        "Content-Type: application/json\r\n\r\n"
        f"{json.dumps(opts)}\r\n".encode())
    parts.append(
        f"--{BOUNDARY}\r\n"
        'Content-Disposition: form-data; name="file"; filename="package.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n".encode())
    parts.append(zip_bytes)
    parts.append(f"\r\n--{BOUNDARY}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        f"{url}/services/data/v{API}/metadata/deployRequest",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": f"multipart/form-data; boundary={BOUNDARY}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)
    except HTTPError as e:
        raise SystemExit(f"deploy request rejected: HTTP {e.code}\n"
                         f"{e.read().decode(errors='replace')[:1200]}") from None


def poll(url, token, deploy_id, timeout=900):
    started = time.time()
    last = None
    while time.time() - started < timeout:
        req = urllib.request.Request(
            f"{url}/services/data/v{API}/metadata/deployRequest/"
            f"{deploy_id}?includeDetails=true",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
        res = d.get("deployResult", d)
        state = res.get("status")
        done = res.get("done")
        msg = (f"  {state}  {res.get('numberComponentsDeployed', 0)}"
               f"/{res.get('numberComponentsTotal', 0)} components")
        if msg != last:
            print(msg)
            last = msg
        if done:
            return res
        time.sleep(5)
    raise SystemExit("deployment did not finish within the timeout")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check-only", action="store_true",
                    help="Validate against the org without changing anything")
    ap.add_argument("--save-zip", help="Also write the generated package to this path")
    ap.add_argument("--standard-only", action="store_true",
                    help="Deploy only custom fields on standard objects. Use on "
                         "editions that do not permit custom objects.")
    ap.add_argument("--test-level", default=None,
                    choices=["RunLocalTests", "RunAllTestsInOrg", "NoTestRun"],
                    help="Usually unnecessary. Production orgs reject NoTestRun.")
    args = ap.parse_args()

    zip_bytes, manifest = build_package(args.standard_only)
    print(f"package: {len(manifest['objects'])} objects, "
          f"{len(manifest['permissionSets'])} permission sets, "
          f"{len(zip_bytes) / 1024:.1f} KB")
    for o in manifest["objects"]:
        print(f"    {o}")
    if manifest.get("skipped"):
        print(f"  skipped (custom objects): {', '.join(manifest['skipped'])}")

    if args.save_zip:
        Path(args.save_zip).write_bytes(zip_bytes)
        print(f"  saved {args.save_zip}")

    url, token = resolve()
    print(f"\ntarget org: {url}")
    print("mode: validate only (no changes)" if args.check_only else "mode: DEPLOY")

    r = post_deploy(url, token, zip_bytes, args.check_only, args.test_level)
    deploy_id = r.get("id") or r.get("deployResult", {}).get("id")
    print(f"deployment {deploy_id}\n")

    res = poll(url, token, deploy_id)
    if res.get("success"):
        print(f"\nSUCCESS - {res.get('numberComponentsDeployed')} components "
              f"{'validated' if args.check_only else 'deployed'}")
        if not args.check_only:
            print("\nNext:")
            print("  1. Assign the RY_Demo_Import permission set to your user")
            print("     (Setup > Permission Sets > RY Demo Import > Manage Assignments)")
            print("  2. python tools/import_salesforce.py --preflight")
        return

    print("\nFAILED")
    details = res.get("details", {}) or {}
    failures = details.get("componentFailures") or []
    if isinstance(failures, dict):
        failures = [failures]
    for f in failures[:25]:
        print(f"  {f.get('componentType')} {f.get('fullName')}: {f.get('problem')}")
    if not failures:
        print(json.dumps(res, indent=2)[:2000])
    sys.exit(1)


if __name__ == "__main__":
    main()
