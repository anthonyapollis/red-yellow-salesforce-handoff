#!/usr/bin/env python3
"""Builds the Red & Yellow GA4 -> Fabric ingestion flow in a live NiFi.

Companion to build_flow.py, which does the same for Salesforce. Together they
are the two halves of the acquisition story: GA4 says how someone arrived,
Salesforce says what happened to them afterwards, and the warehouse joins the
two on campaign and landing page.

Why this builder uses the GA4 Data API
----------------------------------------
The Data API is a direct GA4 route: BigQuery is not required, and runReport
returns the aggregated acquisition dimensions and metrics this warehouse joins
on. GA4 also offers a native BigQuery export for richer event-level analysis.
That second route is intentionally documented as an alternative rather than
silently represented as a live source in this NiFi flow.

docs/GA4_TO_FABRIC_EXTENSION.md sets out both paths, their grain and when each is right.

Idempotent: re-running deletes and rebuilds the process group.

    python build_ga4_flow.py --user <uuid> --password <pw>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://localhost:8443/nifi-api"
PG_NAME = "RY_GA4_to_Fabric"
CTX_NAME = "RY_GA4_Fabric_Params"

# One request per report. GA4's Data API is dimension/metric shaped rather than
# table shaped, so each of these is a separate runReport call and lands as its
# own bronze dataset.
GA4_REPORTS = {
    # How people arrive. The join key back to the CRM is the campaign name,
    # which UTM tagging puts on both sides.
    "acquisition": {
        "dimensions": "date,sessionDefaultChannelGroup,sessionSource,"
                      "sessionMedium,sessionCampaignName",
        "metrics": "sessions,engagedSessions,totalUsers,newUsers,"
                   "userEngagementDuration,keyEvents",
    },
    # What they landed on. This is the SEO surface: organic landing pages are
    # the pages worth optimising, and their enquiry rate is the target.
    "landing_pages": {
        "dimensions": "date,landingPagePlusQueryString,"
                      "sessionDefaultChannelGroup,deviceCategory",
        "metrics": "sessions,engagedSessions,bounceRate,"
                   "averageSessionDuration,keyEvents",
    },
    # Which programme pages get looked at, so demand can be read before an
    # enquiry is ever submitted.
    "programme_pages": {
        "dimensions": "date,pagePath,pageTitle",
        "metrics": "screenPageViews,userEngagementDuration,keyEvents",
    },
}

PARAMETERS = [
    ("ga4.property.id", "", False,
     "GA4 property id, digits only - the Data API path is properties/<id>:runReport"),
    ("ga4.api.url", "https://analyticsdata.googleapis.com/v1beta", False,
     "GA4 Data API base"),
    ("ga4.access.token", "", True,
     "Short-lived GA4 bearer token. Supply it through a secure token broker that "
     "uses the service-account JWT flow; never treat a private key as a client secret."),
    ("ga4.lookback.days", "3", False,
     "Re-pull this many days each run. GA4 restates recent days, so a pure "
     "high-water mark would freeze the first, incomplete version of a day."),
    ("fabric.onelake.account", "onelake", False, "OneLake storage account name"),
    ("fabric.onelake.suffix", "fabric.microsoft.com", False,
     "Endpoint suffix - points the ADLS processors at OneLake, not Azure Blob"),
    ("fabric.workspace", "WS_RedAndYellow", False, "Fabric workspace = OneLake filesystem"),
    ("fabric.tenant.id", "", True, "Entra ID tenant"),
    ("fabric.sp.id", "", True, "Service principal application id"),
    ("fabric.sp.secret", "", True, "Service principal secret"),
    ("bronze.path", "LH_RedAndYellow.Lakehouse/Files/bronze/ga4", False,
     "Landing path inside the lakehouse"),
]


def nifi_password(given):
    if given:
        return given
    f = pathlib.Path("C:/Apache/NIFI_LOGIN.txt")
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("password:"):
                return line.split(":", 1)[1].strip()
    return ""


def nifi_user(given):
    if given:
        return given
    f = pathlib.Path("C:/Apache/NIFI_LOGIN.txt")
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("username:"):
                return line.split(":", 1)[1].strip()
    return ""


class Nifi:
    def __init__(self, user, password):
        self.s = requests.Session()
        self.s.verify = False
        r = self.s.post(BASE + "/access/token",
                        data={"username": user, "password": password},
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=30)
        r.raise_for_status()
        self.s.headers["Authorization"] = "Bearer " + r.text

    def get(self, p):
        r = self.s.get(BASE + p, timeout=60)
        r.raise_for_status()
        return r.json()

    def post(self, p, body):
        r = self.s.post(BASE + p, json=body, timeout=60)
        if not r.ok:
            raise SystemExit(f"POST {p} -> {r.status_code}\n{r.text[:600]}")
        return r.json()

    def put(self, p, body):
        r = self.s.put(BASE + p, json=body, timeout=60)
        if not r.ok:
            raise SystemExit(f"PUT {p} -> {r.status_code}\n{r.text[:600]}")
        return r.json()

    def delete(self, p, params=None):
        return self.s.delete(BASE + p, params=params or {}, timeout=60)


def rev(entity):
    r = dict(entity["revision"])
    r["clientId"] = "ry-ga4-builder"
    return r


def set_props(n, kind, entity, wanted, label, dynamic=None):
    """Set declared and dynamic properties after descriptor introspection.

    Headers and record attributes are dynamic NiFi properties, so they do not
    appear in the descriptor map. Declared properties remain validated.
    """
    fresh = n.get(f"/{kind}/{entity['id']}")
    descriptors = fresh["component"]["config"]["descriptors"] \
        if kind == "processors" else fresh["component"]["descriptors"]
    by_display = {d["displayName"]: k for k, d in descriptors.items()}
    props, missing = {}, []
    for display, value in wanted.items():
        key = by_display.get(display) or (display if display in descriptors else None)
        if key is None:
            missing.append(display)
        else:
            props[key] = value
    if missing:
        raise SystemExit(
            f"{label}: these properties do not exist on this NiFi build: {missing}\n"
            f"available: {sorted(by_display)[:40]}")
    props.update(dynamic or {})
    body = {"revision": rev(fresh), "component": {"id": entity["id"]}}
    if kind == "processors":
        body["component"]["config"] = {"properties": props}
    else:
        body["component"]["properties"] = props
    return n.put(f"/{kind}/{entity['id']}", body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="")
    ap.add_argument("--password", default="")
    args = ap.parse_args()

    user, pw = nifi_user(args.user), nifi_password(args.password)
    if not (user and pw):
        sys.exit("need --user and --password (or C:/Apache/NIFI_LOGIN.txt)")

    n = Nifi(user, pw)
    root = n.get("/flow/process-groups/root")["processGroupFlow"]["id"]
    print(f"connected. root = {root}")

    # -- idempotency: remove a previous build ---------------------------------
    existing = n.get(f"/flow/process-groups/{root}")["processGroupFlow"]["flow"]["processGroups"]
    for g in existing:
        if g["component"]["name"] == PG_NAME:
            gid = g["id"]
            # Controller services must be disabled before the group will delete,
            # otherwise NiFi answers 409 and leaves a duplicate on the canvas.
            n.put(f"/flow/process-groups/{gid}/controller-services",
                  {"id": gid, "state": "DISABLED", "disconnectedNodeAcknowledged": False})
            fresh = n.get(f"/process-groups/{gid}")
            n.delete(f"/process-groups/{gid}",
                     {"version": fresh["revision"]["version"], "clientId": "ry-ga4-builder"})
            print(f"  removed previous {PG_NAME}")

    # -- parameter context ----------------------------------------------------
    ctx = None
    for c in n.get("/flow/parameter-contexts")["parameterContexts"]:
        if c["component"]["name"] == CTX_NAME:
            ctx = c
    params = [{"parameter": {"name": nm, "value": val, "sensitive": sens,
                             "description": desc}}
              for nm, val, sens, desc in PARAMETERS]
    if ctx:
        n.put(f"/parameter-contexts/{ctx['id']}", {
            "revision": rev(ctx),
            "component": {"id": ctx["id"], "name": CTX_NAME, "parameters": params}})
        ctx_id = ctx["id"]
        print(f"  parameter context {CTX_NAME} updated")
    else:
        e = n.post("/parameter-contexts", {
            "revision": {"version": 0, "clientId": "ry-ga4-builder"},
            "component": {"name": CTX_NAME, "parameters": params,
                          "description": "GA4 Data API and OneLake credentials "
                                         "for the Red & Yellow acquisition flow"}})
        ctx_id = e["id"]
        print(f"  parameter context {CTX_NAME} created")

    def new_group(parent, name, x, y, comments):
        e = n.post(f"/process-groups/{parent}/process-groups", {
            "revision": {"version": 0, "clientId": "ry-ga4-builder"},
            "component": {"name": name, "position": {"x": float(x), "y": float(y)},
                          "comments": comments}})
        return e["id"]

    pg_id = new_group(root, PG_NAME, 240, 1240,
                      "Red & Yellow: GA4 -> OneLake bronze -> Fabric.\n"
                      "How an audience arrived, landing beside how they "
                      "converted in Salesforce.\n"
                      "Built idempotently by nifi/build_ga4_flow.py.")
    cur = n.get(f"/process-groups/{pg_id}")
    n.put(f"/process-groups/{pg_id}", {
        "revision": rev(cur),
        "component": {"id": pg_id,
                      "parameterContext": {"id": ctx_id,
                                           "component": {"id": ctx_id, "name": CTX_NAME}}}})
    print(f"process group {PG_NAME} ({pg_id}) bound to {CTX_NAME}")

    # -- controller services --------------------------------------------------
    def cs(cls, name, props=None):
        e = n.post(f"/process-groups/{pg_id}/controller-services", {
            "revision": {"version": 0, "clientId": "ry-ga4-builder"},
            "component": {"type": cls, "name": name}})
        if props:
            e = set_props(n, "controller-services", e, props, name)
        print(f"  service  {name}")
        return e["id"]

    cs("org.apache.nifi.web.client.provider.service.StandardWebClientServiceProvider",
       "RY_GA4_WebClient")

    # Google service accounts use a signed JWT assertion, not the OAuth client
    # credentials grant. A token broker obtains a short-lived access token with
    # the official Google auth library and writes ga4.access.token securely.
    # Keeping signing outside this NiFi flow avoids storing an RSA private key in
    # a generic OAuth client-secret property.
    adls = cs("org.apache.nifi.services.azure.storage.ADLSCredentialsControllerService",
              "RY_GA4_OneLake_Credentials",
              {"Storage Account Name": "#{fabric.onelake.account}",
               "Endpoint Suffix": "#{fabric.onelake.suffix}",
               "Service Principal Tenant ID": "#{fabric.tenant.id}",
               "Service Principal Client ID": "#{fabric.sp.id}",
               "Service Principal Client Secret": "#{fabric.sp.secret}"})

    extract_id = new_group(pg_id, "01_Extract_GA4", 40, 40,
                           "One runReport call per dataset, on a rolling "
                           "lookback because GA4 restates recent days.")
    land_id = new_group(pg_id, "02_Land_OneLake_Bronze", 640, 40,
                        "Writes each report to bronze/ga4/<report>/"
                        "ingest_date=<date>.")

    n.post(f"/process-groups/{pg_id}/labels", {
        "revision": {"version": 0, "clientId": "ry-ga4-builder"},
        "component": {"position": {"x": 40.0, "y": 340.0},
                      "width": 1180.0, "height": 150.0,
                      "label": "Red & Yellow - GA4 to Fabric\n\n"
                               "01 Extract   one runReport per dataset, rolling "
                               "3-day lookback (GA4 restates recent days, so a "
                               "high-water mark would freeze day one's partial "
                               "numbers)\n"
                               "02 Land      bronze/ga4/<report>/ingest_date=<date>\n\n"
                               "Joins to the Salesforce flow on campaign name via "
                               "UTM tagging, closing the loop from search "
                               "impression to enrolment.\n"
                               "Credentials come from RY_GA4_Fabric_Params; "
                               "sensitive parameters are empty in source control.",
                      "style": {"font-size": "13px"}}})

    def proc(cls, name, x, y, props=None, dynamic=None, sched=None, autoterm=None, group=None):
        e = n.post(f"/process-groups/{group or pg_id}/processors", {
            "revision": {"version": 0, "clientId": "ry-ga4-builder"},
            "component": {"type": cls, "name": name,
                          "position": {"x": float(x), "y": float(y)}}})
        if props or dynamic:
            e = set_props(n, "processors", e, props or {}, name, dynamic)
        cfg = {}
        if sched:
            cfg.update(sched)
        if autoterm:
            cfg["autoTerminatedRelationships"] = autoterm
        if cfg:
            fresh = n.get(f"/processors/{e['id']}")
            e = n.put(f"/processors/{e['id']}",
                      {"revision": rev(fresh),
                       "component": {"id": e["id"], "config": cfg}})
        print(f"    processor {name}")
        return e["id"]

    # -- 01 extract -----------------------------------------------------------
    # Each response remains one JSON document. Concatenating independent
    # runReport responses would make invalid JSON and lose report identity.
    out_port = n.post(f"/process-groups/{extract_id}/output-ports", {
        "revision": {"version": 0, "clientId": "ry-ga4-builder"},
        "component": {"name": "ga4_reports", "position": {"x": 920.0, "y": 340.0},
                      "comments": "GA4 runReport JSON with a report attribute."}})
    in_port = n.post(f"/process-groups/{land_id}/input-ports", {
        "revision": {"version": 0, "clientId": "ry-ga4-builder"},
        "component": {"name": "ga4_to_land", "position": {"x": 0.0, "y": 40.0}}})

    def conn(group, src, dst, rels, src_type="PROCESSOR", dst_type="PROCESSOR"):
        n.post(f"/process-groups/{group}/connections", {
            "revision": {"version": 0, "clientId": "ry-ga4-builder"},
            "component": {
                "source": {"id": src["id"], "groupId": src.get("_group", group), "type": src_type},
                "destination": {"id": dst["id"], "groupId": dst.get("_group", group), "type": dst_type},
                "selectedRelationships": rels,
                "backPressureObjectThreshold": 20000,
                "backPressureDataSizeThreshold": "1 GB",
            },
        })

    y = 40
    for report, spec in GA4_REPORTS.items():
        body = {
            "dateRanges": [{"startDate": "#{ga4.lookback.days}daysAgo", "endDate": "today"}],
            "dimensions": [{"name": d} for d in spec["dimensions"].split(",")],
            "metrics": [{"name": m} for m in spec["metrics"].split(",")],
            "limit": 100000,
        }
        gen = proc("org.apache.nifi.processors.standard.GenerateFlowFile",
                   f"Request_{report}", 40, y,
                   {"Custom Text": json.dumps(body, indent=2), "Batch Size": "1"},
                   dynamic={"ga4.report": report, "filename": f"{report}_${{now():format('yyyyMMddHHmmss')}}.json"},
                   sched={"schedulingPeriod": "6 hours", "schedulingStrategy": "TIMER_DRIVEN"},
                   group=extract_id)
        invoke = proc("org.apache.nifi.processors.standard.InvokeHTTP",
                      f"RunReport_{report}", 350, y,
                      {"HTTP Method": "POST",
                       "HTTP URL": "#{ga4.api.url}/properties/#{ga4.property.id}:runReport",
                       "Request Content-Type": "application/json",
                       "Request Body Enabled": "true"},
                      dynamic={"Authorization": "Bearer #{ga4.access.token}"},
                      autoterm=["original", "retry", "no retry", "failure"],
                      group=extract_id)
        tag = proc("org.apache.nifi.processors.attributes.UpdateAttribute",
                   f"Tag_{report}", 650, y,
                   dynamic={"ga4.report": report,
                            "filename": f"{report}_${{now():format('yyyyMMddHHmmss')}}.json"},
                   group=extract_id)
        conn(extract_id, {"id": gen}, {"id": invoke}, ["success"])
        conn(extract_id, {"id": invoke}, {"id": tag}, ["response"])
        conn(extract_id, {"id": tag}, out_port, ["success"], dst_type="OUTPUT_PORT")
        y += 200

    # -- 02 land --------------------------------------------------------------
    land = proc("org.apache.nifi.processors.azure.storage.PutAzureDataLakeStorage",
                "Write_Bronze", 380, 40,
                {"ADLS Credentials": adls,
                 "Filesystem Name": "#{fabric.workspace}",
                 "Directory Name": "#{bronze.path}/${ga4.report}/ingest_date=${now():format('yyyy-MM-dd')}",
                 "File Name": "${filename}",
                 "Conflict Resolution Strategy": "replace"},
                autoterm=["success", "failure"], group=land_id)

    conn(pg_id, dict(out_port, _group=extract_id), dict(in_port, _group=land_id),
         [""], src_type="OUTPUT_PORT", dst_type="INPUT_PORT")
    conn(land_id, in_port, {"id": land}, [""], src_type="INPUT_PORT")
    print(f"  connections {len(GA4_REPORTS) * 3 + 2} across 2 stage groups")

    print(f"\nBuilt {PG_NAME}.")
    print("  open it at https://localhost:8443/nifi and it appears beside "
          "RY_Salesforce_to_Fabric on the root canvas.")
    print("  Processors stay invalid until the sensitive parameters are "
          "supplied - the intended state for a repository.")


if __name__ == "__main__":
    main()
