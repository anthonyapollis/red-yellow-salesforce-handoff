#!/usr/bin/env python3
"""Resolves a Salesforce access token from the environment.

Two supported routes, neither of which puts a credential in this repository:

  1. SF_CLIENT_ID + SF_CLIENT_SECRET  - OAuth client-credentials grant against
     an External Client App. Preferred: the token refreshes itself, and the
     same two values also drive the NiFi flow's parameter context, so one
     setup serves both the importer and the pipeline.

  2. SF_ACCESS_TOKEN + SF_INSTANCE_URL - a token you already hold. Simplest for
     a one-off, but Salesforce session tokens expire, so this is the route that
     mysteriously stops working tomorrow.

    python sf_auth.py            # prints whether auth is configured and works
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from urllib.error import HTTPError

TOKEN_PATH = "/services/oauth2/token"


def resolve():
    """Return (instance_url, access_token). Raises SystemExit with guidance."""
    token = os.environ.get("SF_ACCESS_TOKEN", "").strip()
    url = os.environ.get("SF_INSTANCE_URL", "").strip().rstrip("/")

    if token and url:
        return url, token

    cid = os.environ.get("SF_CLIENT_ID", "").strip()
    secret = os.environ.get("SF_CLIENT_SECRET", "").strip()
    login = os.environ.get("SF_LOGIN_URL", "").strip().rstrip("/")

    if not (cid and secret and login):
        raise SystemExit(
            "No Salesforce credentials in the environment.\n\n"
            "Set either:\n"
            "  SF_CLIENT_ID / SF_CLIENT_SECRET / SF_LOGIN_URL   (preferred)\n"
            "or:\n"
            "  SF_ACCESS_TOKEN / SF_INSTANCE_URL\n\n"
            "SF_LOGIN_URL is your My Domain URL, e.g.\n"
            "  https://business-data-62022.my.salesforce.com")

    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": secret,
    }).encode()
    req = urllib.request.Request(
        login + TOKEN_PATH, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
    except HTTPError as e:
        detail = e.read().decode(errors="replace")[:600]
        raise SystemExit(
            f"Token request failed: HTTP {e.code}\n{detail}\n\n"
            "Common causes: the External Client App has no 'Run As' user set for "
            "the client-credentials flow, the app is not enabled for it, or "
            "SF_LOGIN_URL is not the org's My Domain URL.") from None

    return d["instance_url"].rstrip("/"), d["access_token"]


def whoami(url, token, version="62.0"):
    req = urllib.request.Request(
        f"{url}/services/data/v{version}/chatter/users/me",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    url, token = resolve()
    print(f"instance: {url}")
    try:
        me = whoami(url, token)
        print(f"connected as: {me.get('displayName')} <{me.get('email')}>")
        print(f"org id: {me.get('companyName')}")
        print("\nAuth works.")
    except HTTPError as e:
        raise SystemExit(f"Token rejected by the org: HTTP {e.code}\n"
                         f"{e.read().decode(errors='replace')[:400]}")


if __name__ == "__main__":
    main()
