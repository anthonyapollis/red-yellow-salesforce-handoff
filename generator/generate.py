#!/usr/bin/env python3
"""Red & Yellow synthetic CRM + academic data generator.

Generates a marketing-to-graduation dataset shaped by erds/03_salesforce_canonical.mmd,
anchored to the REAL catalogue transcribed in data/catalogue/ (83 programmes,
89 offerings, 47 dated intakes). Everything about people is synthetic.

Two deliberate design choices:

1. Defects are injected on purpose and recorded in a ground-truth manifest
   (warehouse/_truth/defects.json). dbt tests are then scored against that
   manifest, so "our data quality tests work" becomes a measured claim rather
   than an assertion.

2. Principled blanks from the catalogue are preserved, never invented. An
   "Enquire for price" offering keeps a null fee - it does not become zero.

Usage:
    python generate.py --scale full          # ~2.4M people, ~12M rows
    python generate.py --scale dev           # ~200k people, fast iteration
    python generate.py --scale smoke         # ~10k people, seconds
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
import sa_reference as ref  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CATALOGUE = REPO / "data" / "catalogue"
OUT = REPO / "warehouse" / "raw"
TRUTH = REPO / "warehouse" / "_truth"

SEED = 20260908
EPOCH = date(2022, 1, 1)          # four years of marketing history
TODAY = date(2026, 9, 8)          # capture date used across the handoff
LOAD_TS = datetime(2026, 9, 8, 20, 0, 0)

SCALES = {
    "smoke": dict(leads=8_000, direct_contacts=2_000, campaigns=40),
    "dev": dict(leads=150_000, direct_contacts=50_000, campaigns=180),
    "full": dict(leads=1_500_000, direct_contacts=900_000, campaigns=480),
}

# Defect rates. Each is recorded in the truth manifest so dbt can be scored.
DEFECTS = dict(
    email_case=0.070,          # LERATO@gmail.com / Lerato@Gmail.com
    email_whitespace=0.025,    # trailing / leading spaces
    email_malformed=0.011,     # missing @, trailing comma
    email_missing=0.032,
    phone_format_drift=0.340,  # +27 vs 0 vs spaced vs bracketed
    phone_missing=0.055,
    name_case=0.045,           # ALL CAPS / lowercase
    name_whitespace=0.030,
    duplicate_person=0.026,    # same human, second record
    province_variant=0.060,    # cape town / CPT / Kaapstad
    province_missing=0.040,
    orphan_fk=0.004,           # FK pointing at a record that does not exist
    negative_fee=0.002,
    fee_missing=0.030,
    date_inversion=0.006,      # enrolled before applied
    dup_campaign_member=0.015,
    late_arriving=0.020,       # source_updated_at after loaded_at
)

SALESFORCE_TABLES = {
    "campaign", "campaign_member", "lead", "contact", "opportunity",
    "programme_enquiry", "application",
}

rng = np.random.default_rng(SEED)
_defect_log = {}


def note(kind, n):
    _defect_log[kind] = _defect_log.get(kind, 0) + int(n)


def weighted(pairs, size):
    """Draw `size` values from [(value, weight), ...]."""
    vals = np.array([p[0] for p in pairs], dtype=object)
    w = np.array([p[1] for p in pairs], dtype=float)
    return vals[rng.choice(len(vals), size=size, p=w / w.sum())]


def mask(n, rate):
    return rng.random(n) < rate


def rand_days(n, start, end):
    """Random dates as numpy datetime64[D], vectorised."""
    s = np.datetime64(start)
    span = max((end - start).days, 1)
    return s + rng.integers(0, span, size=n).astype("timedelta64[D]")


def write(df, name):
    """Write one raw table to Parquet with integration metadata attached."""
    OUT.mkdir(parents=True, exist_ok=True)
    n = len(df)

    # Every integrated record carries provenance - required by the ERD notes.
    df = df.copy()
    df["source_system"] = "SALESFORCE" if name in SALESFORCE_TABLES else "ACADEMIC"
    if "_src_updated" in df.columns:
        df["source_updated_at"] = pd.to_datetime(df.pop("_src_updated"))
    else:
        df["source_updated_at"] = LOAD_TS
    df["loaded_at"] = LOAD_TS
    df["is_deleted"] = df.pop("_deleted") if "_deleted" in df.columns else False

    path = OUT / f"{name}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path, compression="snappy")
    mb = path.stat().st_size / 1024 / 1024
    print(f"  {name:<22} {n:>10,} rows {mb:>8.1f} MB")
    return n, mb


# --------------------------------------------------------------------------
# dirt
# --------------------------------------------------------------------------

def dirty_emails(first, last, n):
    dom = weighted(ref.EMAIL_DOMAINS, n)
    sep = rng.choice([".", "", "_"], size=n, p=[0.62, 0.28, 0.10])
    num = np.where(mask(n, 0.30), rng.integers(1, 999, n).astype(str), "")
    local = pd.Series([f"{f}{s}{l}{x}".lower().replace(" ", "")
                       for f, s, l, x in zip(first, sep, last, num)], dtype=object)

    # Real people do not share an inbox. Drawing names from a realistic SA pool
    # of ~60 first names x ~44 surnames collides constantly, so disambiguate the
    # way Gmail users actually do - thabo.nkosi, then thabo.nkosi1, thabo.nkosi2.
    # Without this the warehouse sees ~680k "duplicate humans" that are simply
    # different people who were handed the same address.
    dupe_rank = local.groupby(local).cumcount()
    local = local + np.where(dupe_rank > 0, dupe_rank.astype(str), "")

    base = pd.Series([f"{lo}@{d}" for lo, d in zip(local, dom)], dtype=object)

    m = mask(n, DEFECTS["email_case"])
    note("email_case", m.sum())
    base[m] = base[m].str.upper()

    m = mask(n, DEFECTS["email_whitespace"])
    note("email_whitespace", m.sum())
    base[m] = " " + base[m].astype(str) + "  "

    m = mask(n, DEFECTS["email_malformed"])
    note("email_malformed", m.sum())
    if m.sum():
        vals = base[m].astype(str)
        flip = rng.random(m.sum()) < 0.5
        base[m] = np.where(flip, vals.str.replace("@", "", n=1, regex=False), vals + ",")

    m = mask(n, DEFECTS["email_missing"])
    note("email_missing", m.sum())
    base[m] = None
    return base


def uniquify_emails(s):
    """Make every non-null address unique across a whole table.

    dirty_emails() only disambiguates within one call. Contacts are assembled
    from two independent draws - converted leads and direct enquiries - and both
    draws mint the same "thabo.nkosi", "thabo.nkosi1" ladder from the same name
    pool, so they collide almost completely once concatenated. That produced a
    2x false-duplicate rate downstream. Uniqueness has to be enforced on the
    final population, not per draw.
    """
    norm = s.astype(str).str.strip().str.lower()
    rank = norm.groupby(norm).cumcount()
    m = (rank > 0) & s.notna()
    if m.any():
        fixed = []
        for v, r in zip(s[m].astype(str), rank[m]):
            if "@" in v:
                a, b = v.rsplit("@", 1)
                fixed.append(f"{a}x{r}@{b}")
            else:
                fixed.append(f"{v}x{r}")
        s = s.copy()
        s[m] = fixed
    return s


def dirty_phones(n):
    core = rng.integers(600_000_000, 899_999_999, n).astype(str)
    style = rng.random(n)
    out = np.empty(n, dtype=object)
    a = style < 0.34
    b = (style >= 0.34) & (style < 0.62)
    c = (style >= 0.62) & (style < 0.84)
    d = (style >= 0.84) & (style < 0.95)
    e = style >= 0.95
    out[a] = ["+27" + x for x in core[a]]
    out[b] = ["0" + x for x in core[b]]
    out[c] = [f"0{x[:2]} {x[2:5]} {x[5:]}" for x in core[c]]
    out[d] = [f"+27 {x[:2]} {x[2:5]} {x[5:]}" for x in core[d]]
    out[e] = [f"({x[:3]}) {x[3:6]}-{x[6:]}" for x in core[e]]
    note("phone_format_drift", int((~a).sum()))

    s = pd.Series(out, dtype=object)
    m = mask(n, DEFECTS["phone_missing"])
    note("phone_missing", m.sum())
    s[m] = None
    return s


def dirty_names(names, n):
    s = pd.Series(names, dtype=object)
    m = mask(n, DEFECTS["name_case"])
    note("name_case", m.sum())
    if m.sum():
        vals = s[m].astype(str)
        flip = rng.random(m.sum()) < 0.5
        s[m] = np.where(flip, vals.str.upper(), vals.str.lower())

    m = mask(n, DEFECTS["name_whitespace"])
    note("name_whitespace", m.sum())
    s[m] = s[m].astype(str) + "  "
    return s


PROVINCE_VARIANTS = {
    "Western Cape": ["western cape", "WESTERN CAPE", "W Cape", "WC", "Wes-Kaap"],
    "Gauteng": ["gauteng", "GAUTENG", "GP", "Gauteng ", "Jhb"],
    "KwaZulu-Natal": ["kwazulu natal", "KZN", "Kwazulu-Natal", "KwaZulu Natal"],
    "Eastern Cape": ["eastern cape", "EC", "E Cape", "Oos-Kaap"],
}


def dirty_province(prov, n):
    s = pd.Series(prov, dtype=object)
    m = mask(n, DEFECTS["province_variant"])
    changed = 0
    for key, opts in PROVINCE_VARIANTS.items():
        sel = m & (s.values == key)
        k = int(sel.sum())
        if k:
            s[sel] = np.array(opts, dtype=object)[rng.integers(0, len(opts), k)]
            changed += k
    note("province_variant", changed)

    m = mask(n, DEFECTS["province_missing"])
    note("province_missing", m.sum())
    s[m] = None
    return s


def src_updated(n, base_dates):
    """source_updated_at, with a slice arriving after loaded_at - the replication trap."""
    ts = pd.to_datetime(pd.Series(base_dates)) + pd.to_timedelta(rng.integers(0, 86400, n), unit="s")
    m = mask(n, DEFECTS["late_arriving"])
    note("late_arriving", m.sum())
    if m.sum():
        ts[m] = LOAD_TS + pd.to_timedelta(rng.integers(60, 86400, int(m.sum())), unit="s")
    return ts


# --------------------------------------------------------------------------
# latent structure
#
# Without this every outcome is an independent weighted draw, so nothing in the
# data predicts anything: conversion is the same rate whatever the source,
# withdrawal is the same rate whatever the attendance, and a model trained on it
# scores AUC 0.50 - which is exactly what happened before this existed. Real
# pipelines have structure, and analysis of a dataset without it is analysis of
# noise dressed as insight.
#
# Each person gets a latent propensity built from things known about them, plus
# unexplained variation. Outcomes are then drawn from that propensity rather
# than from a flat rate. The noise term matters: it keeps the ceiling realistic,
# so a model lands somewhere defensible instead of at a suspicious 0.99.
# --------------------------------------------------------------------------

SOURCE_EFFECT = {
    "Referral": 0.95, "Open Day": 0.75, "Webinar": 0.55, "Career Expo": 0.35,
    "Web Enquiry Form": 0.10, "Inbound Call": 0.30, "Partner": 0.20,
    "Google Ads": -0.15, "Paid Social": -0.40, "Walk-in": -0.55,
}
PROVINCE_EFFECT = {
    "Western Cape": 0.45, "Gauteng": 0.30, "KwaZulu-Natal": 0.05,
    "Eastern Cape": -0.15, "Free State": -0.20, "Limpopo": -0.30,
    "Mpumalanga": -0.25, "North West": -0.30, "Northern Cape": -0.35,
    "Outside South Africa": -0.60,
}
CHANNEL_EFFECT = {
    "Referral": 0.55, "Open day": 0.45, "Email": 0.25, "Webinar": 0.30,
    "Organic search": 0.20, "Career expo": 0.15, "Paid social": -0.20,
    "Google Ads": -0.10, "Radio": -0.35, "Billboard": -0.40, "Print": -0.45,
}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def lead_propensity(source, province, has_email, has_phone, channel, n):
    """Latent score for how likely this enquiry is to become an enrolment."""
    z = np.full(n, -1.35)  # base rate lives here
    z += np.array([SOURCE_EFFECT.get(s, 0.0) for s in source])
    z += np.array([PROVINCE_EFFECT.get(p, -0.2) for p in province])
    z += np.where(has_email, 0.45, -0.55)
    z += np.where(has_phone, 0.25, -0.30)
    z += np.array([CHANNEL_EFFECT.get(c, 0.0) if c else -0.15 for c in channel])
    # Unexplained variation - the part no feature set will ever recover.
    z += rng.normal(0, 0.85, n)
    return z


def people(n, prefix):
    """Shared person-shaped columns for leads and contacts."""
    first = weighted(ref.FIRST_NAMES, n)
    last = weighted(ref.SURNAMES, n)
    prov = weighted(ref.PROVINCES, n)
    city = np.array([ref.CITY_BY_PROVINCE[p][rng.integers(0, len(ref.CITY_BY_PROVINCE[p]))]
                     for p in prov], dtype=object)
    return dict(
        first_name=dirty_names(first, n),
        last_name=dirty_names(last, n),
        email=dirty_emails(first, last, n),
        phone=dirty_phones(n),
        city=city,
        province=dirty_province(prov, n),
        _clean_first=first,
        _clean_last=last,
        # The undirtied province, so latent effects key off the real value
        # rather than whichever spelling variant this row happened to get.
        _clean_province=prov,
    )


def ids(prefix, n, start=1):
    """Vectorised external IDs, e.g. RY-LEAD-00000042."""
    return np.char.add(prefix, np.char.zfill((np.arange(start, start + n)).astype("U9"), 8))


class ChunkWriter:
    """Streams a large fact table to Parquet so we never hold it all in RAM."""

    def __init__(self, name):
        self.name = name
        self.path = OUT / f"{name}.parquet"
        self.writer = None
        self.rows = 0

    def add(self, df):
        df = df.copy()
        df["source_system"] = "SALESFORCE" if self.name in SALESFORCE_TABLES else "ACADEMIC"
        if "_src_updated" in df.columns:
            df["source_updated_at"] = pd.to_datetime(df.pop("_src_updated"))
        else:
            df["source_updated_at"] = LOAD_TS
        df["loaded_at"] = LOAD_TS
        df["is_deleted"] = df.pop("_deleted") if "_deleted" in df.columns else False

        table = pa.Table.from_pandas(df, preserve_index=False)
        if self.writer is None:
            OUT.mkdir(parents=True, exist_ok=True)
            self.writer = pq.ParquetWriter(self.path, table.schema, compression="snappy")
        self.writer.write_table(table)
        self.rows += len(df)

    def close(self):
        if self.writer:
            self.writer.close()
        mb = self.path.stat().st_size / 1024 / 1024
        print(f"  {self.name:<22} {self.rows:>10,} rows {mb:>8.1f} MB")
        return self.rows, mb


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------

def build_campaigns(n):
    cid = ids("RY-CAMP-", n)
    start = rand_days(n, EPOCH, TODAY)
    channel = weighted(ref.CAMPAIGN_CHANNELS, n)
    theme = np.array(ref.CAMPAIGN_THEMES, dtype=object)[rng.integers(0, len(ref.CAMPAIGN_THEMES), n)]
    year = pd.to_datetime(start).year.astype(str)

    # Spend is lognormal - a few big brand campaigns, a long tail of small ones.
    # Calibrated so cost-per-enrolment lands in the R1.5k-R6k band that private
    # SA tertiary providers actually see. An earlier draw put CPE at R180, which
    # would have been the first number an interviewer challenged.
    spend = np.round(rng.lognormal(mean=13.6, sigma=0.7, size=n), 2)
    m = mask(n, DEFECTS["fee_missing"])
    note("fee_missing", m.sum())
    spend = pd.Series(spend)
    spend[m] = None

    df = pd.DataFrame({
        "campaign_external_id": cid,
        "campaign_name": [f"{t} {y}" for t, y in zip(theme, year)],
        "channel": channel,
        "start_date": start,
        "end_date": start + rng.integers(14, 120, n).astype("timedelta64[D]"),
        "spend_zar": spend,
        "is_active": rng.random(n) < 0.35,
        "_src_updated": src_updated(n, start),
    })
    return df


def build_leads(n, campaigns):
    p = people(n, "lead")
    created = rand_days(n, EPOCH, TODAY)
    source = weighted(ref.LEAD_SOURCES, n)
    camp_idx = rng.integers(0, len(campaigns), n)
    has_camp = mask(n, 0.72)
    camp = np.where(has_camp, campaigns["campaign_external_id"].values[camp_idx], None)
    camp_channel = np.where(has_camp, campaigns["channel"].values[camp_idx], None)

    # Latent propensity drives status, rather than status being an independent
    # draw. A referral from the Western Cape with an email now behaves
    # differently from a walk-in with neither - which is what makes the data
    # analysable and the downstream model meaningful.
    prop = lead_propensity(source, p["_clean_province"],
                           p["email"].notna().values,
                           p["phone"].notna().values, camp_channel, n)
    conv_p = sigmoid(prop)
    is_conv = rng.random(n) < conv_p * 0.42

    status = np.where(
        is_conv, "Converted",
        weighted([("Open - Not Contacted", 22), ("Working - Contacted", 26),
                  ("Nurture", 16), ("Qualified", 14), ("Unqualified", 8)], n))
    # Qualified/Working skew toward the higher-propensity unconverted leads.
    hi = (~is_conv) & (prop > np.quantile(prop, 0.72))
    status = np.where(hi & (rng.random(n) < 0.45), "Qualified", status)

    df = pd.DataFrame({
        "lead_external_id": ids("RY-LEAD-", n),
        "first_name": p["first_name"],
        "last_name": p["last_name"],
        "email": p["email"],
        "phone": p["phone"],
        "city": p["city"],
        "province": p["province"],
        "lead_source": source,
        "lead_status": status,
        "campaign_external_id": camp,
        "created_date": created,
        "_src_updated": src_updated(n, created),
    })
    df["_clean_first"] = p["_clean_first"]
    df["_clean_last"] = p["_clean_last"]
    # Carried, not written: the latent score flows to contacts and on through
    # the funnel so every stage inherits the same person's propensity.
    df["_propensity"] = prop
    return df


def build_contacts(leads, n_direct):
    """Contacts = converted leads + people who arrived without a lead record."""
    conv = leads[leads["lead_status"].values == "Converted"].reset_index(drop=True)
    n_conv = len(conv)
    n = n_conv + n_direct

    direct = people(n_direct, "contact")
    created_conv = conv["created_date"].values + rng.integers(1, 45, n_conv).astype("timedelta64[D]")
    created_direct = rand_days(n_direct, EPOCH, TODAY)

    df = pd.DataFrame({
        "contact_external_id": ids("RY-CONT-", n),
        "first_name": pd.concat([conv["first_name"], direct["first_name"]], ignore_index=True),
        "last_name": pd.concat([conv["last_name"], direct["last_name"]], ignore_index=True),
        "email": pd.concat([conv["email"], direct["email"]], ignore_index=True),
        "phone": pd.concat([conv["phone"], direct["phone"]], ignore_index=True),
        "city": np.concatenate([conv["city"].values, direct["city"]]),
        "province": pd.concat([conv["province"], pd.Series(direct["province"])], ignore_index=True),
        "converted_from_lead_id": np.concatenate([conv["lead_external_id"].values,
                                                  np.full(n_direct, None, dtype=object)]),
        "created_date": np.concatenate([created_conv, created_direct]),
    })
    df["email"] = uniquify_emails(df["email"])
    # Converted contacts inherit their lead's propensity; people who arrived
    # without a lead record get their own draw, slightly higher on average
    # because walking in already signals intent.
    df["_propensity"] = np.concatenate([
        conv["_propensity"].values,
        lead_propensity(np.full(n_direct, "Web Enquiry Form"),
                        direct["_clean_province"],
                        pd.Series(direct["email"]).notna().values,
                        pd.Series(direct["phone"]).notna().values,
                        np.full(n_direct, None), n_direct) + 0.35,
    ])
    df["_src_updated"] = src_updated(n, df["created_date"].values)

    # Duplicate humans: the same person enquiring twice, months apart, with a
    # slightly different email. This is the single most common real CRM defect.
    k = int(n * DEFECTS["duplicate_person"])
    if k:
        pick = df.sample(k, random_state=SEED).reset_index(drop=True)
        pick["contact_external_id"] = ids("RY-CONT-", k, start=n + 1)

        # Two realistic duplicate shapes, so matching has to handle both:
        #   half re-submitted the web form months later  -> identical email
        #   half phoned in and no email was captured     -> phone + surname only
        by_phone = rng.random(k) < 0.5
        pick.loc[by_phone, "email"] = None
        pick["created_date"] = pick["created_date"].values + rng.integers(30, 400, k).astype("timedelta64[D]")
        pick["converted_from_lead_id"] = None
        note("duplicate_person", k)
        df = pd.concat([df, pick], ignore_index=True)
    return df


def build_campaign_members(campaigns, leads, contacts, per_campaign):
    """Streamed - this is the widest fan-out table in the model."""
    cw = ChunkWriter("campaign_member")
    camp_ids = campaigns["campaign_external_id"].values
    lead_ids = leads["lead_external_id"].values
    cont_ids = contacts["contact_external_id"].values
    seq = 1

    for block in np.array_split(np.arange(len(camp_ids)), max(len(camp_ids) // 40, 1)):
        n = int(per_campaign * len(block))
        if n <= 0:
            continue
        c = camp_ids[rng.choice(block, n)]
        use_lead = rng.random(n) < 0.62
        lid = np.where(use_lead, lead_ids[rng.integers(0, len(lead_ids), n)], None)
        cid = np.where(~use_lead, cont_ids[rng.integers(0, len(cont_ids), n)], None)
        responded = rand_days(n, EPOCH, TODAY)

        df = pd.DataFrame({
            "campaign_member_external_id": ids("RY-CM-", n, start=seq),
            "campaign_external_id": c,
            "lead_external_id": lid,
            "contact_external_id": cid,
            "response_status": weighted(ref.RESPONSE_STATUSES, n),
            "first_responded_date": responded,
            "_src_updated": src_updated(n, responded),
        })
        seq += n

        # Same person added to the same campaign twice - a real Salesforce duplicate.
        k = int(n * DEFECTS["dup_campaign_member"])
        if k:
            dup = df.sample(k, random_state=SEED + seq)
            note("dup_campaign_member", k)
            df = pd.concat([df, dup], ignore_index=True)

        cw.add(df)
    return cw.close()


def build_enquiries(contacts, offerings, n):
    cont_ids = contacts["contact_external_id"].values
    off_ids = offerings["RY_External_ID__c"].values
    when = rand_days(n, EPOCH, TODAY)

    cid = cont_ids[rng.integers(0, len(cont_ids), n)]
    # Orphan FKs: a contact that was deleted in the source but whose enquiry remains.
    m = mask(n, DEFECTS["orphan_fk"])
    note("orphan_fk", m.sum())
    cid = np.where(m, np.array(["RY-CONT-99999999"], dtype=object)[0], cid)

    return pd.DataFrame({
        "enquiry_external_id": ids("RY-ENQ-", n),
        "contact_external_id": cid,
        "offering_external_id": off_ids[rng.integers(0, len(off_ids), n)],
        "enquiry_date": when,
        "channel": weighted(ref.CAMPAIGN_CHANNELS, n),
        "status": weighted([("New", 34), ("Contacted", 30), ("Qualified", 20), ("Closed", 16)], n),
        "_src_updated": src_updated(n, when),
    })


def build_opportunities(contacts, intakes, offerings, campaigns, n):
    # Opportunities are not a random sample of contacts: higher-propensity
    # people are the ones who progress. Sampling with weight is what puts a
    # real relationship between the CRM's features and its outcomes.
    w = sigmoid(contacts["_propensity"].values)
    w = w / w.sum()
    pick = rng.choice(len(contacts), size=n, replace=True, p=w)
    contacts = contacts.iloc[pick].reset_index(drop=True)
    cont_ids = contacts["contact_external_id"].values
    intake_ids = intakes["RY_External_ID__c"].values
    camp_ids = campaigns["campaign_external_id"].values

    # Advertised fee drives expected value; "Enquire" offerings stay null on purpose.
    fee_by_offer = dict(zip(offerings["RY_External_ID__c"], offerings["Advertised_Fee_ZAR__c"]))
    offer_by_intake = dict(zip(intakes["RY_External_ID__c"], intakes["Offering_Key"]))

    chosen_intake = intake_ids[rng.integers(0, len(intake_ids), n)]
    adv = np.array([fee_by_offer.get(offer_by_intake.get(i), np.nan) for i in chosen_intake],
                   dtype=float)
    # Real discounting: bursaries, early-bird, corporate rates.
    value = np.round(adv * rng.uniform(0.72, 1.0, n), 2)

    value = pd.Series(value)
    m = mask(n, DEFECTS["negative_fee"])
    note("negative_fee", m.sum())
    value[m] = -value[m].abs()

    created = rand_days(n, EPOCH, TODAY)
    # Stage depends on the person's propensity and on how expensive the
    # offering is - a R27,000 postgraduate programme closes less readily than a
    # short course, which is the relationship a sales team would recognise.
    prop = contacts["_propensity"].values
    price_drag = -np.nan_to_num(adv, nan=8000.0) / 60000.0
    z = prop + price_drag + rng.normal(0, 0.7, n)
    r = rng.random(n)
    won_p = sigmoid(z) * 0.55
    stage = np.where(
        r < won_p, "Closed Won",
        np.where(r < won_p + 0.16, "Closed Lost",
                 weighted([("Enquiry", 16), ("Qualification", 20),
                           ("Application Sent", 22), ("Application Received", 22),
                           ("Offer Made", 20)], n)))

    return pd.DataFrame({
        "opportunity_external_id": ids("RY-OPP-", n),
        # Already sampled by propensity above - re-randomising here would throw
        # that away and put the outcome back on a contact chosen at random.
        "contact_external_id": cont_ids,
        "_propensity": prop,
        "intake_external_id": chosen_intake,
        "primary_campaign_external_id": np.where(mask(n, 0.66),
                                                 camp_ids[rng.integers(0, len(camp_ids), n)], None),
        "stage_name": stage,
        "expected_value_zar": value,
        "created_date": created,
        "close_date": created + rng.integers(7, 180, n).astype("timedelta64[D]"),
        "is_won": stage == "Closed Won",
        "_src_updated": src_updated(n, created),
    })


def build_applications(opps, n):
    """One application per opportunity that got past qualification."""
    eligible = opps[~np.isin(opps["stage_name"].values, ["Enquiry", "Qualification"])]
    eligible = eligible.sample(min(n, len(eligible)), random_state=SEED).reset_index(drop=True)
    n = len(eligible)

    submitted = eligible["created_date"].values + rng.integers(3, 60, n).astype("timedelta64[D]")

    # Acceptance follows the applicant's propensity; withdrawal is more common
    # among the weakly-engaged. Independent draws here would sever the link
    # between everything upstream and the outcome that matters.
    aprop = eligible["_propensity"].values
    z = aprop + 0.55 + rng.normal(0, 0.6, n)
    r = rng.random(n)
    acc_p = sigmoid(z) * 0.86
    status = np.where(
        r < acc_p, "Accepted",
        np.where(r < acc_p + 0.10 * sigmoid(-aprop) + 0.05, "Declined",
                 weighted([("Submitted", 30), ("Under Review", 26),
                           ("Withdrawn", 24), ("Waitlisted", 20)], n)))
    decision = submitted + rng.integers(5, 45, n).astype("timedelta64[D]")

    df = pd.DataFrame({
        "application_external_id": ids("RY-APP-", n),
        "_propensity": aprop,
        "opportunity_external_id": eligible["opportunity_external_id"].values,
        "contact_external_id": eligible["contact_external_id"].values,
        "intake_external_id": eligible["intake_external_id"].values,
        "submitted_date": submitted,
        "decision_date": decision,
        "status": status,
        "_src_updated": src_updated(n, submitted),
    })

    # Decision recorded before submission - a real data-entry defect.
    m = mask(n, DEFECTS["date_inversion"])
    note("date_inversion", m.sum())
    df.loc[m, "decision_date"] = df.loc[m, "submitted_date"].values - np.timedelta64(9, "D")
    return df


def build_students_enrolments(apps, intakes, offerings):
    accepted = apps[apps["status"].values == "Accepted"].reset_index(drop=True)

    # One human is ONE student, however many times they are accepted. An earlier
    # version minted a student per accepted application, so anyone who came back
    # for a second qualification appeared twice - which inflates the student
    # count and breaks the one-student-per-contact rule the ERD states. Multiple
    # study episodes belong on enrolments, which hang off the single student.
    accepted = accepted.sort_values(["contact_external_id", "decision_date"])
    first = accepted.drop_duplicates("contact_external_id", keep="first").reset_index(drop=True)
    n = len(first)

    students = pd.DataFrame({
        "student_external_id": ids("RY-STU-", n),
        "contact_external_id": first["contact_external_id"].values,
        "student_number": [f"RY{2022 + int(i) % 5}{i:06d}" for i in range(1, n + 1)],
        "enrolled_first_date": first["decision_date"].values,
        "_src_updated": src_updated(n, first["decision_date"].values),
    })

    # Every accepted application still becomes an enrolment; it just points at
    # the student for its contact rather than at a student of its own.
    student_by_contact = dict(zip(students["contact_external_id"],
                                  students["student_external_id"]))
    accepted = accepted.reset_index(drop=True)
    n = len(accepted)

    fee_by_offer = dict(zip(offerings["RY_External_ID__c"], offerings["Advertised_Fee_ZAR__c"]))
    offer_by_intake = dict(zip(intakes["RY_External_ID__c"], intakes["Offering_Key"]))
    adv = np.array([fee_by_offer.get(offer_by_intake.get(i), np.nan)
                    for i in accepted["intake_external_id"].values], dtype=float)
    agreed = pd.Series(np.round(adv * rng.uniform(0.70, 1.0, n), 2))

    m = mask(n, DEFECTS["fee_missing"])
    note("fee_missing", m.sum())
    agreed[m] = None

    # Engagement is the latent that drives BOTH attendance and withdrawal, so
    # the early-weeks signal genuinely predicts the outcome rather than the two
    # being independent draws that happen to sit in the same table.
    engagement = (accepted["_propensity"].values * 0.8
                  + rng.normal(0, 0.7, n))
    wd_p = sigmoid(-engagement) * 0.30
    r_e = rng.random(n)
    enrol_status = np.where(
        r_e < wd_p, "Withdrawn",
        np.where(r_e < wd_p + 0.07, "Deferred",
                 np.where(r_e < wd_p + 0.12, "On Hold",
                          np.where(rng.random(n) < 0.34, "Completed", "Active"))))

    enrolled = accepted["decision_date"].values + rng.integers(5, 70, n).astype("timedelta64[D]")
    enrolments = pd.DataFrame({
        "enrolment_external_id": ids("RY-ENR-", n),
        "student_external_id": accepted["contact_external_id"].map(student_by_contact).values,
        "application_external_id": accepted["application_external_id"].values,
        "intake_external_id": accepted["intake_external_id"].values,
        "enrolled_date": enrolled,
        "agreed_fee_zar": agreed,
        "status": enrol_status,
        "_src_updated": src_updated(n, enrolled),
    })
    enrolments["_engagement"] = engagement

    # Enrolled before the application was even submitted.
    m = mask(n, DEFECTS["date_inversion"])
    note("date_inversion", m.sum())
    enrolments.loc[m, "enrolled_date"] = (
        accepted.loc[m, "submitted_date"].values - np.timedelta64(14, "D"))
    return students, enrolments


def build_progress(enrolments, chunk=40_000):
    """Weekly attendance/assessment per enrolment. The largest table by far."""
    cw = ChunkWriter("student_progress")
    seq = 1
    for start in range(0, len(enrolments), chunk):
        blk = enrolments.iloc[start:start + chunk]
        weeks = rng.integers(6, 20, len(blk))
        eid = np.repeat(blk["enrolment_external_id"].values, weeks)
        base = np.repeat(blk["enrolled_date"].values, weeks)
        wk = np.concatenate([np.arange(w) for w in weeks])
        week_start = base + (wk * 7).astype("timedelta64[D]")
        n = len(eid)

        # Attendance decays a little each week and is centred on the student's
        # engagement, so a disengaged student looks different from week one.
        eng = np.repeat(blk["_engagement"].values, weeks)
        att = np.clip(rng.normal(80 + eng * 9 - wk * 0.9, 11, n), 0, 100).round(1)
        assess = np.clip(att * 0.62 + rng.normal(22, 13, n), 0, 100).round(1)
        overdue = rng.poisson(np.clip((70 - att) / 22, 0, 6)).astype(int)
        risk = np.where(att < 55, "High", np.where(att < 72, "Medium", "Low"))

        att_s = pd.Series(att)
        m = mask(n, 0.02)
        note("attendance_missing", m.sum())
        att_s[m] = None

        cw.add(pd.DataFrame({
            "progress_external_id": ids("RY-PRG-", n, start=seq),
            "enrolment_external_id": eid,
            "week_start": week_start,
            "week_number": wk + 1,
            "attendance_pct": att_s,
            "assessment_average_pct": assess,
            "overdue_assignments": overdue,
            "risk_band": risk,
            "_src_updated": pd.to_datetime(pd.Series(week_start)) + pd.Timedelta(days=2),
        }))
        seq += n
    return cw.close()


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scale", choices=list(SCALES), default="full")
    args = ap.parse_args()
    cfg = SCALES[args.scale]
    t0 = time.time()

    print(f"\nRed & Yellow synthetic generator - scale={args.scale}, seed={SEED}")
    print(f"output: {OUT}\n")

    programmes = pd.read_csv(CATALOGUE / "RY_Programme__c.csv")
    offerings = pd.read_csv(CATALOGUE / "RY_Programme_Offering__c.csv")
    intakes = pd.read_csv(CATALOGUE / "RY_Intake__c.csv")
    print(f"catalogue anchor: {len(programmes)} programmes, "
          f"{len(offerings)} offerings, {len(intakes)} intakes (real, transcribed)\n")

    total = 0
    campaigns = build_campaigns(cfg["campaigns"])
    total += write(campaigns, "campaign")[0]

    leads = build_leads(cfg["leads"], campaigns)
    total += write(leads.drop(columns=["_clean_first", "_clean_last", "_propensity"]), "lead")[0]

    contacts = build_contacts(leads, cfg["direct_contacts"])
    total += write(contacts.drop(columns=["_propensity"]), "contact")[0]

    total += build_campaign_members(campaigns, leads, contacts, per_campaign=5_200)[0]

    n_enq = int(len(contacts) * 0.55)
    total += write(build_enquiries(contacts, offerings, n_enq), "programme_enquiry")[0]

    n_opp = int(len(contacts) * 0.62)
    opps = build_opportunities(contacts, intakes, offerings, campaigns, n_opp)
    total += write(opps.drop(columns=["_propensity"]), "opportunity")[0]

    apps = build_applications(opps, int(n_opp * 0.72))
    total += write(apps.drop(columns=["_propensity"]), "application")[0]

    students, enrolments = build_students_enrolments(apps, intakes, offerings)
    total += write(students, "student")[0]
    total += write(enrolments.drop(columns=["_engagement"]), "enrolment")[0]

    total += build_progress(enrolments)[0]

    # Catalogue dimensions pass through untouched - they are real, not generated.
    for name, df in [("programme", programmes), ("programme_offering", offerings),
                     ("intake", intakes)]:
        total += write(df, name)[0]

    TRUTH.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scale": args.scale,
        "seed": SEED,
        "total_rows": int(total),
        "configured_defect_rates": DEFECTS,
        "injected_defect_counts": dict(sorted(_defect_log.items())),
    }
    (TRUTH / "defects.json").write_text(json.dumps(manifest, indent=2))

    print(f"\n  {'TOTAL':<22} {total:>10,} rows")
    print(f"\ninjected defects (ground truth for dbt scoring):")
    for k, v in sorted(_defect_log.items()):
        print(f"  {k:<24} {v:>10,}")
    print(f"\nmanifest: {TRUTH / 'defects.json'}")
    print(f"elapsed:  {time.time() - t0:.1f}s\n")


if __name__ == "__main__":
    main()
