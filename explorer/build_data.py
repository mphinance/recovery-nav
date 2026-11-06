#!/usr/bin/env python3
"""Build docs/data/*.json for the Wisconsin Opioid Settlement Explorer.

Source: Wisconsin Watch tracker CSV (fetched into explorer/data/raw/, which is
gitignored; the source repo carries no license, so the raw file is never
committed). Standard library plus PyYAML only.

Usage: .venv/bin/python explorer/build_data.py [--no-download]
"""
import csv
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RAW = ROOT / "data" / "raw" / "cleaned_data_all.csv"
OUT = REPO / "docs" / "data"
CSV_URL = ("https://raw.githubusercontent.com/Wisconsin-Watch/"
           "2026_06_23_Opioid_Settlment_Find_Expense/main/data/cleaned_data_all.csv")
YEARS = ["2022", "2023", "2024", "2025"]
METHOD_VERSION = "1.0"
SOURCE_NAME = "Wisconsin Watch tracker"
SOURCE_PAGE = "https://github.com/Wisconsin-Watch/2026_06_23_Opioid_Settlment_Find_Expense"

# Obvious spelling errors in the source's government names. Applied openly and flagged.
NAME_FIXES = {"Mantiwoc County": "Manitowoc County",
              "Pleasant Prarie, village": "Pleasant Prairie, village"}

PLACEHOLDERS = re.compile(
    r"^(none|none reported\.?|none in 2025\.?|n/?a|optional questions not submitted\.?|"
    r"no (expenditures|spending).*|not (reported|provided).*|treatment)$", re.I)

AMT_PAREN = re.compile(r"\(\s*(?:[^()]*?\$\s*(?P<d>[\d,]+(?:\.\d+)?)[^()]*?|(?P<b>\d{1,3}(?:,\d{3})+(?:\.\d+)?))\s*\)")
HEADER_ANY = re.compile(r"Spending\s+\w+\s+between\s+(\d{4})\s+and\s+(\d{4})\s*:\s*", re.I)


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s


def num(s):
    """Parse a money cell. Returns (value|None, ok)."""
    s = (s or "").strip().replace(",", "").replace("$", "")
    if s == "":
        return None, False
    try:
        return float(s), True
    except ValueError:
        return None, False


def fetch(no_download):
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if no_download and RAW.exists():
        return datetime.fromtimestamp(RAW.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    with urllib.request.urlopen(CSV_URL, timeout=60) as r:
        RAW.write_bytes(r.read())
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_categories():
    cfg = yaml.safe_load((ROOT / "categories.yaml").read_text())["categories"]
    rules = [(c["id"], [re.compile(p, re.I) for p in c.get("patterns") or []]) for c in cfg]
    meta = [{"id": c["id"], "label": c["label"], "description": c["description"]} for c in cfg]
    return rules, meta


def categorize(text, rules):
    for cid, pats in rules:
        if any(p.search(text) for p in pats):
            return cid
    return "other"


def clean_phrase(s):
    s = re.sub(r"\s*[\u2014\u2013]\s*", ", ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.lstrip(" ,;.:-")
    s = re.sub(r"^(and|also)\s+", "", s, flags=re.I)
    return s.strip(" ,;")


def parse_items(text, default_period, gov_id, gov_name, rules):
    """Return (items, dollar_signs_total, dollar_signs_parsed, chars_total, chars_priced)."""
    items = []
    raw = (text or "").strip()
    if not raw or PLACEHOLDERS.match(raw):
        return items, 0, 0, 0, 0
    period = default_period
    # Split into blocks by Milwaukee-style headers.
    blocks = []
    pos = 0
    cur_period = default_period
    for m in HEADER_ANY.finditer(raw):
        if m.start() > pos:
            blocks.append((cur_period, raw[pos:m.start()]))
        cur_period = f"{m.group(1)}-{m.group(2)}"
        pos = m.end()
    blocks.append((cur_period, raw[pos:]))
    dollars_total = len(re.findall(r"\$", raw))  # informational
    dollars_parsed = 0
    chars_priced = 0
    for per, blk in blocks:
        last = 0
        for m in AMT_PAREN.finditer(blk):
            seg = blk[last:m.start()]
            last = m.end()
            # keep only the final sentence of the segment
            parts = re.split(r"(?<=[a-z0-9\)])\.\s+(?=[A-Z])", seg)
            phrase = clean_phrase(parts[-1])
            amt, ok = num(m.group("d") or m.group("b"))
            flags = []
            if not phrase:
                phrase = "(no description given)"
                flags.append("no_description")
            if len(phrase) > 100 or phrase.count(",") >= 2:
                flags.append("phrase_may_include_unpriced_items")
            if re.search(r"not specified|\b20(19|20|21)\b", phrase, re.I):
                flags.append("period_or_amount_unclear")
            if m.group("b"):
                flags.append("amount_without_dollar_sign")
            if len(re.findall(r"\$", m.group(0))) > 1:
                flags.append("multiple_amounts_in_parens")
            dollars_parsed += 1
            chars_priced += len(phrase)
            items.append(dict(period=per, text=phrase, amount=amt, flags=flags))
        tail = blk[last:]
        for sent in re.split(r"(?<=[a-z0-9\)\"])\.\s+(?=[A-Z])", tail):
            phrase = clean_phrase(sent)
            if len(phrase) < 4 or PLACEHOLDERS.match(phrase.rstrip(".")):
                continue
            flags = []
            if phrase.count(",") >= 3:
                flags.append("multi_item_text")
            items.append(dict(period=per, text=phrase.rstrip("."), amount=None, flags=flags))
    out = []
    for it in items:
        flags = list(it["flags"])
        if gov_id == "milwaukee-county" and it["period"] in ("2023-2025", "2024-2026"):
            flags.append("program_commitment_overlapping_periods")
        out.append({
            "county_id": gov_id,
            "county_name": gov_name,
            "period_label": it["period"],
            "text": it["text"],
            "amount": it["amount"],
            # multi-topic phrases are not guessed at: they stay in 'other' with a flag
            "category": "other" if "phrase_may_include_unpriced_items" in flags else categorize(it["text"], rules),
            "status": "reported_initiative",
            "source": SOURCE_NAME,
            "flags": flags,
        })
    return out, dollars_total, dollars_parsed, len(raw), chars_priced


def main():
    no_dl = "--no-download" in sys.argv
    retrieved = fetch(no_dl)
    rules, cat_meta = load_categories()
    rows = list(csv.DictReader(RAW.open(encoding="utf-8", newline="")))

    counties, items = [], []
    for row in rows:
        src_name = row["gov_name"].strip()
        name = NAME_FIXES.get(src_name, src_name)
        flags = []
        if name != src_name:
            flags.append("name_corrected_from_source")
        cid = slug(name)
        ctype = "county" if name.endswith("County") else "municipality"
        by_year, tot = {}, {"receipts": 0.0, "disbursements": 0.0, "interest": 0.0}
        for y in YEARS:
            by_year[y] = {}
            for k in ("receipts", "disbursements", "interest"):
                v, ok = num(row[f"{y}_{k}"])
                if not ok:
                    flags.append(f"missing_{y}_{k}")
                by_year[y][k] = v
                tot[k] += v or 0.0
        bal, okb = num(row["dec_2025_balance"])
        if not okb:
            flags.append("missing_balance")
        denom = tot["receipts"] + tot["interest"]
        pct = tot["disbursements"] / denom if denom else None
        src_pct, okp = num(row["percentage spent"])
        if okp and pct is not None and abs(pct - src_pct) > 0.0005:
            flags.append("pct_spent_differs_from_source")
        if bal is not None:
            delta = round(tot["receipts"] + tot["interest"] - tot["disbursements"] - bal, 2)
            if abs(delta) > 1.0:
                flags.append("balance_mismatch")
        if all((by_year[y]["interest"] or 0) == 0 for y in YEARS):
            flags.append("no_interest_reported")
        e25, e24 = row["2025 Expenditures"].strip(), row["2022, 2023, 2024 expenditures"].strip()
        if (not e25 or PLACEHOLDERS.match(e25)) and (not e24 or PLACEHOLDERS.match(e24)):
            flags.append("no_expenditure_text")
        link = row["doc_link"].strip()
        if link and "documentcloud.org" not in link:
            flags.append("report_url_not_documentcloud")
        note_l = row["notes"].lower()
        if re.search(r"dec(ember|\.)? 2025 balance does not include.{0,30}interest|interest.{0,30}(not included|excluded)", note_l):
            flags.append("interest_excluded")
        if re.search(r"not subtracted|not included|taken out of the account in 2026", note_l) and "interest_excluded" not in flags:
            flags.append("balance_timing_note")
        if cid == "milwaukee-county":
            flags.append("initiatives_overlap_periods")
        counties.append({
            "id": cid, "name": name, "type": ctype,
            "receipts_total": round(tot["receipts"], 2),
            "disbursements_total": round(tot["disbursements"], 2),
            "interest_total": round(tot["interest"], 2),
            "balance_dec_2025": bal,
            "pct_spent": None if pct is None else round(pct, 6),
            "by_year": by_year,
            "report_url": link or None,
            "source": SOURCE_NAME,
            "source_notes": row["notes"].strip() or None,
            "flags": flags,
        })
        for text, per in ((e25, "2025"), (e24, "2022-2024")):
            its, *_ = parse_items(text, per, cid, name, rules)
            items.extend(its)

    cats_used = {c["id"] for c in cat_meta}
    assert all(i["category"] in cats_used for i in items)
    tr = sum(c["receipts_total"] for c in counties)
    td = sum(c["disbursements_total"] for c in counties)
    ti = sum(c["interest_total"] for c in counties)
    tb = sum(c["balance_dec_2025"] or 0 for c in counties)
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [{"name": SOURCE_NAME, "url": SOURCE_PAGE, "retrieved_at": retrieved},
                    {"name": "County and municipal filings linked per government (report_url)",
                     "url": None, "retrieved_at": None}],
        "totals": {"receipts": round(tr, 2), "disbursements": round(td, 2),
                   "interest": round(ti, 2), "balance": round(tb, 2),
                   "governments": len(counties)},
        "caveats": [
            "Figures are as self-reported by each government to the state and compiled by Wisconsin Watch; they have not been independently audited.",
            "Receipts, disbursements and interest cover 2022 through 2025; the balance is as of December 31, 2025.",
            "Percent spent is disbursements divided by receipts plus interest, recomputed from the reported figures.",
            "Spending items are initiatives as the government described them in its report. They are not confirmed cash disbursements, and most governments listed only some of their spending.",
            "Milwaukee County lists initiatives for 2023 to 2025 and for 2024 to 2026. These are program commitments, the ranges overlap, and the amounts must not be added together or compared with disbursements.",
            "Categories are assigned by transparent keyword rules (explorer/categories.yaml) and may be wrong for individual items.",
            "Item amounts do not sum to a government's disbursements.",
        ],
        "method_version": METHOD_VERSION,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for fn, obj in (("counties.json", counties), ("items.json", items),
                    ("categories.json", cat_meta), ("meta.json", meta)):
        (OUT / fn).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"governments={len(counties)} items={len(items)} priced={sum(1 for i in items if i['amount'] is not None)}")
    print(f"receipts={tr:,.2f} disbursements={td:,.2f} interest={ti:,.2f} balance={tb:,.2f}")


if __name__ == "__main__":
    main()
