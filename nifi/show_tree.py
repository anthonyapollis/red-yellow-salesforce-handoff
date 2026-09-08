#!/usr/bin/env python3
"""Prints the NiFi process-group hierarchy with a direct URL for every group.

The canvas only ever shows one group at a time, so the shape of an instance is
hard to see by clicking. This walks it and prints the tree, with the counts that
matter when something is not running.

    python show_tree.py --user <uuid> --password <pw>
    python show_tree.py --user <uuid> --password <pw> --markdown > FLOW_MAP.md
"""
from __future__ import annotations

import argparse
import sys

import requests
import urllib3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--host", default="localhost:8443")
    ap.add_argument("--markdown", action="store_true", help="Emit a Markdown list")
    args = ap.parse_args()

    base = f"https://{args.host}/nifi-api"
    ui = f"https://{args.host}/nifi/#/process-groups"

    s = requests.Session()
    s.verify = False
    r = s.post(f"{base}/access/token",
               data={"username": args.user, "password": args.password},
               headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    s.headers["Authorization"] = f"Bearer {r.text}"

    def walk(gid, depth=0, name=None):
        f = s.get(f"{base}/flow/process-groups/{gid}", timeout=60).json()["processGroupFlow"]
        nm = name or f["breadcrumb"]["breadcrumb"]["name"]
        flow = f["flow"]
        counts = (f"{len(flow['processors'])} proc, "
                  f"{len(flow['processGroups'])} groups, "
                  f"{len(flow['connections'])} conns")
        if args.markdown:
            pad = "  " * depth
            print(f"{pad}- [{nm}]({ui}/{gid}) - {counts}")
        else:
            pad = "    " * depth
            print(f"{pad}{nm}   ({counts})")
            print(f"{pad}  {ui}/{gid}")
        for g in sorted(flow["processGroups"], key=lambda x: x["component"]["name"]):
            walk(g["id"], depth + 1, g["component"]["name"])

    root = s.get(f"{base}/flow/process-groups/root", timeout=60).json()["processGroupFlow"]["id"]
    walk(root)


if __name__ == "__main__":
    main()
