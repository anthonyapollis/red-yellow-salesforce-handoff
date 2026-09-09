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


def env(name):
    """Read an environment variable, falling back to the Windows User scope.

    `setx` writes to the registry, so only processes started afterwards inherit
    the value. A long-running shell - or any tool holding an environment
    captured before the setx - keeps reporting the variable as unset, which
    looks exactly like "the credentials did not save". Reading HKCU\\Environment
    directly makes the script see what setx actually wrote.
    """
    v = os.environ.get(name, "").strip()
    if v or os.name != "nt":
        return v
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return str(winreg.QueryValueEx(k, name)[0]).strip()
    except (ImportError, OSError, FileNotFoundError):
        return ""


def resolve():
    """Return (instance_url, access_token). Raises SystemExit with guidance."""
    token = env("SF_ACCESS_TOKEN")
    url = env("SF_INSTANCE_URL").rstrip("/")

    if token and url:
        return url, token

    cid = env("SF_CLIENT_ID")
    secret = env("SF_CLIENT_SECRET")
    login = env("SF_LOGIN_URL").rstrip("/")

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
    """Identify the token holder without depending on Chatter.

    The obvious endpoint, /chatter/users/me, returns FUNCTIONALITY_NOT_ENABLED
    in any org without Chatter - which reads like an auth failure when the token
    is actually fine. /services/oauth2/userinfo is always available; a SOQL query
    against User is the fallback if the token lacks the identity scope.
    """
    try:
        req = urllib.request.Request(
            f"{url}/services/oauth2/userinfo",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
        return {"name": d.get("name"), "username": d.get("preferred_username"),
                "email": d.get("email"), "org": d.get("organization_id")}
    except HTTPError:
        q = urllib.parse.quote("SELECT Id, Name, Username FROM User "
                               "WHERE Id = null OR Id != null LIMIT 1")
        req = urllib.request.Request(
            f"{url}/services/data/v{version}/query?q={q}",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            rec = json.load(r)["records"][0]
        return {"name": rec.get("Name"), "username": rec.get("Username"),
                "email": None, "org": None}


def main():
    url, token = resolve()
    print(f"instance: {url}")
    try:
        me = whoami(url, token)
        print(f"connected as: {me.get('username') or me.get('email')}")
        if me.get("name"):
            print(f"name: {me['name']}")
        if me.get("org"):
            print(f"org id: {me['org']}")
        print("\nAuth works.")
    except HTTPError as e:
        raise SystemExit(f"Token rejected by the org: HTTP {e.code}\n"
                         f"{e.read().decode(errors='replace')[:400]}")


if __name__ == "__main__":
    main()
