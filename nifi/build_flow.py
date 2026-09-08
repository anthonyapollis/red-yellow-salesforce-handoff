#!/usr/bin/env python3
"""Builds the Red & Yellow Salesforce -> Fabric ingestion flow in a live NiFi.

Why build the flow over the REST API instead of shipping a flow.json:
a hand-written flow definition is unverifiable until someone imports it, and
NiFi property keys differ between versions. This script introspects each
processor's real property descriptors from the running instance and sets
properties by display name, so it stays correct across NiFi versions and fails
loudly if a property it expects no longer exists.

Idempotent: re-running deletes and rebuilds the process group.

    python build_flow.py --user <uuid> --password <pw>
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://localhost:8443/nifi-api"
PG_NAME = "RY_Salesforce_to_Fabric"
CTX_NAME = "RY_Salesforce_Fabric_Params"

# Salesforce objects to replicate, with the fields the ERD actually needs.
SF_OBJECTS = {
    "Lead": "Id,FirstName,LastName,Email,Phone,State,City,LeadSource,Status,"
            "ConvertedContactId,CreatedDate,SystemModstamp,IsDeleted",
    "Contact": "Id,FirstName,LastName,Email,Phone,MailingState,MailingCity,"
               "AccountId,CreatedDate,SystemModstamp,IsDeleted",
    "Campaign": "Id,Name,Type,Status,StartDate,EndDate,ActualCost,IsActive,"
                "CreatedDate,SystemModstamp,IsDeleted",
    "CampaignMember": "Id,CampaignId,LeadId,ContactId,Status,HasResponded,"
                      "FirstRespondedDate,CreatedDate,SystemModstamp",
    "Opportunity": "Id,Name,AccountId,StageName,Amount,CloseDate,IsWon,IsClosed,"
                   "CampaignId,CreatedDate,SystemModstamp,IsDeleted",
}

PARAMETERS = [
    ("sf.instance.url", "https://business-data-62022.my.salesforce.com", False,
     "Salesforce My Domain URL for the target org"),
    ("sf.api.version", "62.0", False, "Salesforce REST API version"),
    ("sf.token.url", "https://login.salesforce.com/services/oauth2/token", False,
     "OAuth2 token endpoint - swap to test.salesforce.com for a sandbox"),
    ("sf.client.id", "", True, "External Client App consumer key"),
    ("sf.client.secret", "", True, "External Client App consumer secret"),
    ("fabric.onelake.account", "onelake", False, "OneLake storage account name"),
    ("fabric.onelake.suffix", "fabric.microsoft.com", False,
     "Endpoint suffix - this is what points ADLS processors at OneLake instead of Azure Blob"),
    ("fabric.workspace", "WS_RedAndYellow", False, "Fabric workspace = OneLake filesystem"),
    ("fabric.lakehouse", "LH_RedAndYellow", False, "Fabric lakehouse name"),
    ("fabric.tenant.id", "", True, "Entra ID tenant"),
    ("fabric.sp.id", "", True, "Service principal application id"),
    ("fabric.sp.secret", "", True, "Service principal secret"),
    ("bronze.path", "LH_RedAndYellow.Lakehouse/Files/bronze/salesforce", False,
     "Landing path inside the lakehouse"),
]


class Nifi:
    def __init__(self, user, password):
        self.s = requests.Session()
        self.s.verify = False
        r = self.s.post(f"{BASE}/access/token",
                        data={"username": user, "password": password},
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=30)
        r.raise_for_status()
        self.s.headers["Authorization"] = f"Bearer {r.text}"

    def get(self, p):
        r = self.s.get(f"{BASE}{p}", timeout=60)
        r.raise_for_status()
        return r.json()

    def post(self, p, body):
        r = self.s.post(f"{BASE}{p}", json=body, timeout=60)
        if not r.ok:
            sys.exit(f"POST {p} -> {r.status_code}\n{r.text[:900]}")
        return r.json()

    def put(self, p, body):
        r = self.s.put(f"{BASE}{p}", json=body, timeout=60)
        if not r.ok:
            sys.exit(f"PUT {p} -> {r.status_code}\n{r.text[:900]}")
        return r.json()

    def delete(self, p, params=None):
        return self.s.delete(f"{BASE}{p}", params=params, timeout=60)


def rev(entity):
    return {"version": entity["revision"]["version"],
            "clientId": entity["revision"].get("clientId", "ry-builder")}


def set_props(n, kind, entity, wanted, label):
    """Set properties by DISPLAY name, resolving the real key from descriptors.

    Fails loudly on an unknown display name rather than silently writing a
    property NiFi will ignore - the failure mode that makes hand-built flows
    look configured when they are not.
    """
    eid = entity["id"]
    fresh = n.get(f"/{kind}/{eid}")
    descs = fresh["component"]["config"]["descriptors"] if kind == "processors" \
        else fresh["component"]["descriptors"]

    by_display = {d["displayName"]: d["name"] for d in descs.values()}
    props = {}
    unknown = []
    for disp, val in wanted.items():
        key = by_display.get(disp) or (disp if disp in descs else None)
        if key is None:
            unknown.append(disp)
        else:
            props[key] = val
    if unknown:
        sys.exit(f"[{label}] unknown properties: {unknown}\n"
                 f"  available: {sorted(by_display)[:40]}")

    body = {"revision": rev(fresh), "component": {"id": eid}}
    if kind == "processors":
        body["component"]["config"] = {"properties": props}
    else:
        body["component"]["properties"] = props
    return n.put(f"/{kind}/{eid}", body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--host", default="localhost:8443")
    args = ap.parse_args()

    global BASE
    BASE = f"https://{args.host}/nifi-api"
    n = Nifi(args.user, args.password)
    root = n.get("/flow/process-groups/root")["processGroupFlow"]["id"]
    print(f"connected. root process group {root}")

    # -- clean previous build -------------------------------------------------
    for g in n.get(f"/flow/process-groups/{root}")["processGroupFlow"]["flow"]["processGroups"]:
        if g["component"]["name"] == PG_NAME:
            gid = g["id"]
            n.put(f"/flow/process-groups/{gid}",
                  {"id": gid, "state": "STOPPED", "disconnectedNodeAcknowledged": False})
            ent = n.get(f"/process-groups/{gid}")
            n.delete(f"/process-groups/{gid}",
                     params={"version": ent["revision"]["version"], "clientId": "ry-builder"})
            print(f"removed previous {PG_NAME}")

    for c in n.get("/flow/parameter-contexts")["parameterContexts"]:
        if c["component"]["name"] == CTX_NAME:
            n.delete(f"/parameter-contexts/{c['id']}",
                     params={"version": c["revision"]["version"], "clientId": "ry-builder"})
            print(f"removed previous {CTX_NAME}")

    # -- parameter context ----------------------------------------------------
    ctx = n.post("/parameter-contexts", {
        "revision": {"version": 0, "clientId": "ry-builder"},
        "component": {
            "name": CTX_NAME,
            "description": "Salesforce and Fabric OneLake connection parameters. "
                           "Secrets are sensitive and empty in source control.",
            "parameters": [
                {"parameter": {"name": nm, "value": val or None, "sensitive": sens,
                               "description": desc}}
                for nm, val, sens, desc in PARAMETERS
            ],
        },
    })
    ctx_id = ctx["id"]
    print(f"parameter context {CTX_NAME} ({len(PARAMETERS)} parameters)")

    # -- process group --------------------------------------------------------
    pg = n.post(f"/process-groups/{root}/process-groups", {
        "revision": {"version": 0, "clientId": "ry-builder"},
        "component": {"name": PG_NAME, "position": {"x": 100.0, "y": 100.0},
                      "comments": "Salesforce CRM -> OneLake bronze -> Fabric. "
                                  "Built by nifi/build_flow.py."},
    })
    pg_id = pg["id"]
    cur = n.get(f"/process-groups/{pg_id}")
    n.put(f"/process-groups/{pg_id}", {
        "revision": rev(cur),
        "component": {"id": pg_id,
                      "parameterContext": {"id": ctx_id, "component": {"id": ctx_id,
                                                                       "name": CTX_NAME}}},
    })
    print(f"process group {PG_NAME} ({pg_id}) bound to parameter context")

    # -- controller services --------------------------------------------------
    def cs(cls, name, props=None, label=None):
        e = n.post(f"/process-groups/{pg_id}/controller-services", {
            "revision": {"version": 0, "clientId": "ry-builder"},
            "component": {"type": cls, "name": name},
        })
        if props:
            e = set_props(n, "controller-services", e, props, label or name)
        print(f"  service  {name}")
        return e["id"]

    web = cs("org.apache.nifi.web.client.provider.service.StandardWebClientServiceProvider",
             "RY_WebClient")

    oauth = cs("org.apache.nifi.oauth2.StandardOauth2AccessTokenProvider", "RY_Salesforce_OAuth",
               {"Authorization Server URL": "#{sf.token.url}",
                "Grant Type": "Client Credentials",
                "Client ID": "#{sf.client.id}",
                "Client Secret": "#{sf.client.secret}"})

    reader = cs("org.apache.nifi.json.JsonTreeReader", "RY_JsonReader")
    writer = cs("org.apache.nifi.csv.CSVRecordSetWriter", "RY_CsvWriter")

    adls = cs("org.apache.nifi.services.azure.storage.ADLSCredentialsControllerService",
              "RY_OneLake_Credentials",
              {"Storage Account Name": "#{fabric.onelake.account}",
               "Endpoint Suffix": "#{fabric.onelake.suffix}",
               "Service Principal Tenant ID": "#{fabric.tenant.id}",
               "Service Principal Client ID": "#{fabric.sp.id}",
               "Service Principal Client Secret": "#{fabric.sp.secret}"})

    # -- processors -----------------------------------------------------------
    def proc(cls, name, x, y, props=None, sched=None, autoterm=None):
        e = n.post(f"/process-groups/{pg_id}/processors", {
            "revision": {"version": 0, "clientId": "ry-builder"},
            "component": {"type": cls, "name": name, "position": {"x": float(x), "y": float(y)}},
        })
        if props:
            e = set_props(n, "processors", e, props, name)
        cfg = {}
        if sched:
            cfg.update(sched)
        if autoterm:
            cfg["autoTerminatedRelationships"] = autoterm
        if cfg:
            fresh = n.get(f"/processors/{e['id']}")
            e = n.put(f"/processors/{e['id']}",
                      {"revision": rev(fresh), "component": {"id": e["id"], "config": cfg}})
        print(f"  processor {name}")
        return e

    queries = []
    for i, (obj, fields) in enumerate(SF_OBJECTS.items()):
        p = proc("org.apache.nifi.processors.salesforce.QuerySalesforceObject",
                 f"Query {obj}", 0, 40 + i * 190,
                 {"Salesforce Instance URL": "#{sf.instance.url}",
                  "API Version": "#{sf.api.version}",
                  "sObject Name": obj,
                  "Field Names": fields,
                  # Incremental replication: NiFi tracks the high-water mark in
                  # processor state, so a restart does not re-pull history.
                  "Age Field": "SystemModstamp",
                  "Initial Age Start Time": "2022-01-01T00:00:00Z",
                  "Age Delay": "30 sec",
                  "Record Writer": writer,
                  "OAuth2 Access Token Provider": oauth},
                 sched={"schedulingPeriod": "15 min", "schedulingStrategy": "TIMER_DRIVEN"})
        queries.append(p)

    merge = proc("org.apache.nifi.processors.standard.MergeRecord",
                 "Batch Records", 480, 380,
                 {"Record Reader": reader, "Record Writer": writer,
                  "Merge Strategy": "Bin-Packing Algorithm",
                  "Minimum Number of Records": "1000",
                  "Maximum Number of Records": "100000",
                  "Max Bin Age": "5 min"},
                 autoterm=["original", "failure"])

    land = proc("org.apache.nifi.processors.azure.storage.PutAzureDataLakeStorage",
                "Land to OneLake bronze", 900, 380,
                {"ADLS Credentials": adls,
                 "Filesystem Name": "#{fabric.workspace}",
                 "Directory Name": "#{bronze.path}/${sobject:default('unknown')}/"
                                   "ingest_date=${now():format('yyyy-MM-dd')}",
                 "File Name": "${filename}",
                 "Conflict Resolution Strategy": "replace"})

    retry = proc("org.apache.nifi.processors.standard.RetryFlowFile",
                 "Retry OneLake Write", 900, 620,
                 {"Maximum Retries": "3", "Retry Attribute": "onelake.retries"},
                 autoterm=["failure"])

    audit = proc("org.apache.nifi.processors.standard.LogAttribute",
                 "Audit Landed Batch", 1320, 380,
                 {"Log Level": "info",
                  "Attributes to Log": "filename,sobject,record.count,azure.filesystem"},
                 autoterm=["success"])

    # -- connections ----------------------------------------------------------
    def conn(src, dst, rels):
        n.post(f"/process-groups/{pg_id}/connections", {
            "revision": {"version": 0, "clientId": "ry-builder"},
            "component": {
                "source": {"id": src["id"], "groupId": pg_id, "type": "PROCESSOR"},
                "destination": {"id": dst["id"], "groupId": pg_id, "type": "PROCESSOR"},
                "selectedRelationships": rels,
                "backPressureObjectThreshold": 20000,
                "backPressureDataSizeThreshold": "1 GB",
            },
        })

    for q in queries:
        conn(q, merge, ["success"])
    conn(merge, land, ["merged"])
    conn(land, audit, ["success"])
    conn(land, retry, ["failure"])
    conn(retry, land, ["retry"])
    print(f"  connections {len(queries) + 4}")

    # Enable the services that need no secrets; the rest wait for credentials.
    for sid, nm in [(web, "RY_WebClient"), (reader, "RY_JsonReader"), (writer, "RY_CsvWriter")]:
        e = n.get(f"/controller-services/{sid}")
        n.put(f"/controller-services/{sid}/run-status",
              {"revision": rev(e), "state": "ENABLED"})
    print("  enabled credential-free services")

    print(f"\nBuilt {PG_NAME}")
    print(f"  open: https://{args.host}/nifi/#/process-groups/{pg_id}")
    print("  processors are STOPPED and will stay invalid until sf.client.id/secret")
    print("  and fabric.sp.* parameters are supplied in the parameter context.")


if __name__ == "__main__":
    main()
