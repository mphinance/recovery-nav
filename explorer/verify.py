#!/usr/bin/env python3
"""Independent checker for the settlement explorer data.

Written from explorer/SCHEMA.md and the source CSV only. It does not import
any other module from this repository. It recomputes every figure from the
CSV and asserts that docs/data/*.json agrees.

Usage:
    python explorer/verify.py [--csv PATH] [--data DIR] [--root DIR]

CSV lookup order: --csv, $SETTLEMENT_CSV, a few cache locations under
explorer/ and data/, then a download of the published source file.
Exit code 0 means every check passed; 1 means at least one FAIL.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/Wisconsin-Watch/"
    "2026_06_23_Opioid_Settlment_Find_Expense/main/data/cleaned_data_all.csv"
)
YEARS = ["2022", "2023", "2024", "2025"]
KINDS = ["receipts", "disbursements", "interest"]
CATEGORY_STARTER = {
    "jail_moud", "treatment_residential", "treatment_outpatient", "peer_recovery",
    "diversion_courts", "reentry", "harm_reduction_naloxone", "prevention_education",
    "navigation_case_management", "housing_recovery", "enforcement",
    "medical_examiner_epi", "data_analytics", "staff_admin", "other",
}
TOL = 0.011  # one cent of float noise, summed values are rounded to cents
ITEM_TEXT_MISS_LIMIT = 0.02  # share of items allowed to differ from source text
PRIVATE_PATTERNS = [
    r"/home/", r"/Users/", r"C:\\Users", r"research/",
    r"BEGIN [A-Z ]*PRIVATE KEY", r"sk-[A-Za-z0-9]{20,}",
]

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def rec(ok: bool, name: str, detail: str = "") -> bool:
    results.append(("PASS" if ok else "FAIL", name, detail))
    return ok


def warn(name: str, detail: str) -> None:
    results.append(("WARN", name, detail))


def money(s: str | None) -> float | None:
    if s is None:
        return None
    s = str(s).strip().replace("$", "").replace(",", "")
    if s == "" or s.lower() in {"none", "n/a", "na", "nan"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm_text(s: str) -> str:
    s = re.sub(r"\s*[\u2014\u2013]\s*", ", ", s or "")
    s = re.sub(r"[\u2018\u2019\u201c\u201d\"']", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def close(a, b, tol=TOL) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def find_csv(arg: str | None, root: Path) -> tuple[Path | None, str]:
    cands = []
    if arg:
        cands.append(Path(arg))
    if os.environ.get("SETTLEMENT_CSV"):
        cands.append(Path(os.environ["SETTLEMENT_CSV"]))
    for d in ["explorer/cache", "explorer/raw", "explorer/.cache", "data/cache", "data/raw", "explorer"]:
        for p in sorted((root / d).glob("*.csv")) if (root / d).is_dir() else []:
            cands.append(p)
    for c in cands:
        if c.is_file():
            return c, f"local file {c}"
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as r:
            data = r.read().decode("utf-8-sig")
        tmp = root / "explorer" / ".verify-source.csv"
        # keep it out of git and out of docs/: temp file, removed by caller
        tmp.write_text(data, encoding="utf-8")
        return tmp, "downloaded " + SOURCE_URL
    except Exception as e:  # noqa: BLE001
        return None, f"no CSV found and download failed: {e}"


def load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if (r.get("gov_name") or "").strip()]


def row_keys(name: str) -> set[str]:
    base = re.split(r",\s*", name)[0].strip()
    kind = name.split(",")[1].strip() if "," in name else ""
    keys = {slug(name), slug(base)}
    if kind:
        keys |= {slug(f"{base} {kind}"), slug(f"{kind} of {base}")}
    return keys


def expected_for(row: dict) -> dict:
    by_year = {}
    for y in YEARS:
        by_year[y] = {k: money(row.get(f"{y}_{k}")) for k in KINDS}

    def tot(k):
        vals = [by_year[y][k] for y in YEARS if by_year[y][k] is not None]
        return round(sum(vals), 2) if vals else None

    rc, di, it = tot("receipts"), tot("disbursements"), tot("interest")
    denom = (rc or 0) + (it or 0)
    pct = (di / denom) if (di is not None and denom) else None
    name = row["gov_name"].strip()
    return {
        "name": name,
        "type": "county" if name.endswith("County") else "municipality",
        "by_year": by_year,
        "receipts_total": rc,
        "disbursements_total": di,
        "interest_total": it,
        "balance_dec_2025": money(row.get("dec_2025_balance")),
        "pct_spent": pct,
        "src_pct": money(row.get("percentage spent")),
        "text_2025": row.get("2025 Expenditures") or "",
        "text_prior": row.get("2022, 2023, 2024 expenditures") or "",
    }


def is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def check_schema(counties, items, cats, meta):
    bad = []
    for c in counties:
        for f in ["id", "name", "type", "receipts_total", "disbursements_total",
                  "interest_total", "balance_dec_2025", "pct_spent", "by_year",
                  "report_url", "source", "flags"]:
            if f not in c:
                bad.append(f"county {c.get('id')} missing {f}")
        if c.get("type") not in ("county", "municipality"):
            bad.append(f"county {c.get('id')} bad type {c.get('type')!r}")
        for f in ["receipts_total", "disbursements_total", "interest_total",
                  "balance_dec_2025", "pct_spent"]:
            v = c.get(f)
            if v is not None and not is_num(v):
                bad.append(f"county {c.get('id')} {f} not a number: {v!r}")
        if not isinstance(c.get("flags"), list):
            bad.append(f"county {c.get('id')} flags not a list")
        by = c.get("by_year")
        if not isinstance(by, dict) or set(by) != set(YEARS):
            bad.append(f"county {c.get('id')} by_year keys {sorted(by) if isinstance(by, dict) else by}")
        else:
            for y in YEARS:
                if not isinstance(by[y], dict) or set(by[y]) != set(KINDS):
                    bad.append(f"county {c.get('id')} by_year[{y}] keys wrong")
                else:
                    for k in KINDS:
                        if by[y][k] is not None and not is_num(by[y][k]):
                            bad.append(f"county {c.get('id')} by_year[{y}][{k}] not a number")
    for i, it in enumerate(items):
        for f in ["county_id", "period_label", "text", "amount", "category", "status", "source"]:
            if f not in it:
                bad.append(f"item {i} missing {f}")
        if it.get("amount") is not None and not is_num(it.get("amount")):
            bad.append(f"item {i} amount not a number: {it.get('amount')!r}")
    for i, k in enumerate(cats):
        for f in ["id", "label", "description"]:
            if f not in k:
                bad.append(f"category {i} missing {f}")
    for f in ["generated_at", "sources", "totals", "caveats", "method_version"]:
        if f not in meta:
            bad.append(f"meta missing {f}")
    if isinstance(meta.get("totals"), dict):
        for f in ["receipts", "disbursements", "balance", "governments"]:
            if f not in meta["totals"]:
                bad.append(f"meta.totals missing {f}")
    for s in meta.get("sources", []) if isinstance(meta.get("sources"), list) else []:
        for f in ["name", "url", "retrieved_at"]:
            if f not in s:
                bad.append(f"meta.sources entry missing {f}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--data", default=None)
    ap.add_argument("--root", default=None)
    a = ap.parse_args()
    root = Path(a.root) if a.root else Path(__file__).resolve().parent.parent
    data_dir = Path(a.data) if a.data else root / "docs" / "data"

    csv_path, how = find_csv(a.csv, root)
    tmp_created = bool(csv_path and csv_path.name == ".verify-source.csv")
    try:
        if not rec(csv_path is not None, "source CSV available", how):
            return report()
        rows = load_csv(csv_path)
        rec(len(rows) == 87, "CSV has 87 governments", f"found {len(rows)}")
        n_counties = sum(1 for r in rows if r["gov_name"].strip().endswith("County"))
        rec(n_counties == 71 and len(rows) - n_counties == 16,
            "CSV is 71 counties + 16 municipalities", f"{n_counties} + {len(rows) - n_counties}")
        names = [r["gov_name"].strip() for r in rows]
        rec(len(set(names)) == len(names), "CSV gov_name unique")

        files = {n: data_dir / f"{n}.json" for n in ["counties", "items", "categories", "meta"]}
        loaded = {}
        for n, p in files.items():
            if not p.is_file():
                rec(False, f"{n}.json exists", f"missing {p}")
                continue
            d, err = load_json(p)
            if err:
                rec(False, f"{n}.json parses", err)
                continue
            rec(True, f"{n}.json parses")
            loaded[n] = d
        if len(loaded) < 4:
            return report()
        counties, items, cats, meta = (loaded[k] for k in ["counties", "items", "categories", "meta"])
        rec(isinstance(counties, list) and isinstance(items, list) and isinstance(cats, list)
            and isinstance(meta, dict), "top-level JSON types (arrays x3, object)")
        if not (isinstance(counties, list) and isinstance(items, list) and isinstance(cats, list)
                and isinstance(meta, dict)):
            return report()

        # schema
        bad = check_schema(counties, items, cats, meta)
        rec(not bad, "JSON schema conformance (SCHEMA.md v1)",
            "; ".join(bad[:8]) + (f" (+{len(bad) - 8} more)" if len(bad) > 8 else ""))

        # ids
        cids = [c.get("id") for c in counties]
        rec(len(cids) == len(set(cids)), "no duplicate county ids",
            ", ".join(sorted({i for i in cids if cids.count(i) > 1})))
        rec(all(isinstance(i, str) and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in cids),
            "county ids are lowercase slugs")
        kids = [k.get("id") for k in cats]
        rec(len(kids) == len(set(kids)), "no duplicate category ids")
        missing_starter = CATEGORY_STARTER - set(kids)
        rec(not missing_starter, "starter categories all present", ", ".join(sorted(missing_starter)))
        rec(len(counties) == 87, "counties.json has 87 entries", f"found {len(counties)}")
        rec(sum(1 for c in counties if c.get("type") == "county") == 71, "71 counties in JSON")
        rec(sum(1 for c in counties if c.get("type") == "municipality") == 16, "16 municipalities in JSON")

        # match each CSV row to a JSON entry
        by_name = {norm_text(c.get("name", "")): c for c in counties}
        by_id = {c.get("id"): c for c in counties}
        matched, unmatched = {}, []
        for r in rows:
            nm = r["gov_name"].strip()
            c = by_name.get(norm_text(nm))
            if c is None:
                for k in row_keys(nm):
                    if k in by_id:
                        c = by_id[k]
                        break
            if c is None:
                # tolerate corrected source typos (e.g. a misspelled county name)
                cand = difflib.get_close_matches(slug(nm), [k for k in by_id if k], n=1, cutoff=0.9)
                if cand and by_id[cand[0]] not in [m[1] for m in matched.values()]:
                    c = by_id[cand[0]]
                    warn("source name typo corrected in JSON", f"{nm!r} -> {c.get('name')!r}")
            if c is None:
                unmatched.append(nm)
            else:
                matched[nm] = (r, c)
        rec(not unmatched, "every government in the CSV is present in counties.json", ", ".join(unmatched))
        used = [id(c) for _, c in matched.values()]
        rec(len(used) == len(set(used)), "each JSON entry matches exactly one CSV row")
        extra = [c.get("id") for c in counties if id(c) not in set(used)]
        rec(not extra, "no JSON governments absent from the CSV", ", ".join(map(str, extra)))

        # per-government numbers
        errs, null_errs, pct_errs, type_errs, src_pct_diff, bal_diff = [], [], [], [], [], []
        sums = {"receipts": 0.0, "disbursements": 0.0, "balance": 0.0, "interest": 0.0}
        for nm, (r, c) in matched.items():
            e = expected_for(r)
            for f in ["receipts_total", "disbursements_total", "interest_total", "balance_dec_2025"]:
                if not close(e[f], c.get(f)):
                    errs.append(f"{nm}.{f}: csv {e[f]} vs json {c.get(f)}")
                if e[f] is None and c.get(f) == 0:
                    null_errs.append(f"{nm}.{f}")
            for y in YEARS:
                by = c.get("by_year", {}).get(y, {})
                for k in KINDS:
                    ev, jv = e["by_year"][y][k], by.get(k)
                    if not close(ev, jv):
                        errs.append(f"{nm}.by_year.{y}.{k}: csv {ev} vs json {jv}")
                    if ev is None and jv == 0:
                        null_errs.append(f"{nm}.by_year.{y}.{k}")
            if not close(e["pct_spent"], c.get("pct_spent"), 1e-6):
                pct_errs.append(f"{nm}: csv-derived {e['pct_spent']} vs json {c.get('pct_spent')}")
            if c.get("pct_spent") is not None and not (0 <= c["pct_spent"] <= 1.0000001):
                pct_errs.append(f"{nm}: pct_spent out of range {c['pct_spent']}")
            if c.get("type") != e["type"]:
                type_errs.append(f"{nm}: {c.get('type')} vs {e['type']}")
            if e["src_pct"] is not None and e["pct_spent"] is not None and abs(e["src_pct"] - e["pct_spent"]) > 0.005:
                src_pct_diff.append(f"{nm} (source {e['src_pct']:.4f} vs ours {e['pct_spent']:.4f})")
                if "pct_mismatch" not in " ".join(c.get("flags", [])):
                    pass
            if e["balance_dec_2025"] is not None:
                calc = (e["receipts_total"] or 0) + (e["interest_total"] or 0) - (e["disbursements_total"] or 0)
                if abs(calc - e["balance_dec_2025"]) > 1.0:
                    bal_diff.append((nm, round(calc - e["balance_dec_2025"], 2), c))
            sums["receipts"] += e["receipts_total"] or 0
            sums["disbursements"] += e["disbursements_total"] or 0
            sums["interest"] += e["interest_total"] or 0
            sums["balance"] += e["balance_dec_2025"] or 0
        rec(not errs, "per-government totals, balances and by_year match CSV",
            "; ".join(errs[:6]) + (f" (+{len(errs) - 6} more)" if len(errs) > 6 else ""))
        rec(not null_errs, "no nulls turned into zeros", ", ".join(null_errs[:10]))
        rec(not pct_errs, "pct_spent = disbursements / (receipts + interest), within 0 to 1",
            "; ".join(pct_errs[:5]))
        rec(not type_errs, "type county/municipality correct", "; ".join(type_errs[:5]))
        if src_pct_diff:
            warn("our pct_spent vs source 'percentage spent' (>0.5 point apart)",
                 f"{len(src_pct_diff)}: " + "; ".join(src_pct_diff[:5]))
        unflagged = [f"{n} (off {d})" for n, d, c in bal_diff if "balance_mismatch" not in c.get("flags", [])]
        rec(not unflagged, "every receipts+interest-disbursements vs balance gap over $1 carries a balance_mismatch flag",
            "; ".join(unflagged[:6]))
        if bal_diff:
            warn("balance arithmetic gaps over $1 (informational)",
                 f"{len(bal_diff)}: " + "; ".join(f"{n} {d:+}" for n, d, _ in bal_diff[:6]))

        # statewide totals
        t = meta.get("totals", {}) if isinstance(meta.get("totals"), dict) else {}
        for key, exp in [("receipts", sums["receipts"]), ("disbursements", sums["disbursements"]),
                         ("balance", sums["balance"])]:
            ok = is_num(t.get(key)) and abs(t[key] - exp) <= 0.5
            detail = f"csv {exp:,.2f} vs meta {t.get(key)}"
            if not ok and key == "receipts" and is_num(t.get(key)) and abs(t[key] - (exp + sums["interest"])) <= 0.5:
                detail += " (meta appears to include interest; receipts must exclude it, see docs/methodology.md)"
            rec(ok, f"statewide {key} total matches CSV", detail)
        rec(t.get("governments") == 87, "meta.totals.governments == 87", f"meta {t.get('governments')}")
        jr = sum((c.get("receipts_total") or 0) for c in counties)
        jd = sum((c.get("disbursements_total") or 0) for c in counties)
        jb = sum((c.get("balance_dec_2025") or 0) for c in counties)
        rec(abs(jr - t.get("receipts", 0)) <= 0.5 and abs(jd - t.get("disbursements", 0)) <= 0.5
            and abs(jb - t.get("balance", 0)) <= 0.5,
            "meta totals equal the sum of counties.json")

        # items
        cat_ids = set(kids)
        bad_cat = sorted({str(i.get("category")) for i in items if i.get("category") not in cat_ids})
        rec(not bad_cat, "every item category id is valid", ", ".join(bad_cat))
        bad_status = sorted({str(i.get("status")) for i in items if i.get("status") != "reported_initiative"})
        rec(not bad_status, "every item status is reported_initiative", ", ".join(bad_status))
        orphan = sorted({str(i.get("county_id")) for i in items if i.get("county_id") not in by_id})
        rec(not orphan, "every item county_id exists in counties.json", ", ".join(orphan))
        rec(all(isinstance(i.get("text"), str) and i["text"].strip() for i in items), "no empty item text")
        zero_null = [i for i in items if i.get("amount") == 0]
        rec(not zero_null, "no item amount of 0 (absent amounts must be null)", f"{len(zero_null)} items")
        neg = [i for i in items if is_num(i.get("amount")) and i["amount"] < 0]
        rec(not neg, "no negative item amounts")
        src_text_pre = {c["id"]: norm_text((r.get("2025 Expenditures") or "") + " || " + (r.get("2022, 2023, 2024 expenditures") or ""))
                        for r, c in matched.values()}
        dup = {}
        for i in items:
            dup.setdefault((i.get("county_id"), i.get("period_label"), norm_text(i.get("text", "")), i.get("amount")), 0)
            dup[(i.get("county_id"), i.get("period_label"), norm_text(i.get("text", "")), i.get("amount"))] += 1
        dups, dups_src = [], []
        for k, v in dup.items():
            if v > 1:
                st = src_text_pre.get(k[0], "")
                if st.count(k[2].rstrip(". ")) >= v:
                    dups_src.append(k)  # the county itself listed it that many times
                else:
                    dups.append(k)
        rec(not dups, "no duplicate items beyond what the source repeats", f"{len(dups)} duplicates, e.g. {dups[:2]}")
        if dups_src:
            warn("items repeated because the county's own text repeats them", "; ".join(f"{k[0]}: {k[2]!r}" for k in dups_src[:5]))
        iids = [i.get("id") for i in items if "id" in i]
        if iids:
            rec(len(iids) == len(set(iids)), "no duplicate item ids")

        # item provenance against the source text
        src_text = {}
        for nm, (r, c) in matched.items():
            src_text[c["id"]] = norm_text((r.get("2025 Expenditures") or "") + " || " + (r.get("2022, 2023, 2024 expenditures") or ""))
        miss_text, miss_amt = [], []
        for i in items:
            s = src_text.get(i.get("county_id"))
            if s is None:
                continue
            tx = norm_text(i.get("text", ""))
            tx_core = tx.rstrip(".;, ")
            if tx_core and tx_core not in s:
                miss_text.append(f"{i.get('county_id')}: {tx[:60]!r}")
            amt = i.get("amount")
            if is_num(amt):
                forms = {f"{amt:,.2f}", f"{amt:,.0f}", f"{amt:.2f}", f"{amt:.0f}"}
                if not any(f in s.replace("$", "") for f in forms):
                    # 'k' or 'million' shorthand is allowed in the source wording
                    short = [f"{amt / 1000:g}k", f"{amt / 1e6:g} million", f"{amt / 1e6:g}m"]
                    if not any(sh in s.replace(" ", "") or sh in s for sh in short):
                        miss_amt.append(f"{i.get('county_id')}: {amt}")
        share = len(miss_text) / max(len(items), 1)
        rec(share <= ITEM_TEXT_MISS_LIMIT, "item text traces back to the county's own words",
            f"{len(miss_text)} of {len(items)} not found verbatim (limit {ITEM_TEXT_MISS_LIMIT:.0%}); e.g. " + "; ".join(miss_text[:3]))
        rec(not miss_amt, "every non-null item amount appears in the county's source text",
            f"{len(miss_amt)}: " + "; ".join(miss_amt[:5]))

        # item counts: governments with real text should have items; empty text should not
        per = {}
        for i in items:
            per[i.get("county_id")] = per.get(i.get("county_id"), 0) + 1
        empty_markers = {"", "none", "none.", "none in 2025.", "n/a", "none reported.", "optional questions not submitted."}
        no_items_with_text, items_without_text = [], []
        for nm, (r, c) in matched.items():
            texts = [(r.get("2025 Expenditures") or "").strip().lower(), (r.get("2022, 2023, 2024 expenditures") or "").strip().lower()]
            has_text = any(t not in empty_markers for t in texts)
            n = per.get(c["id"], 0)
            if has_text and n == 0 and "no_expenditure_text" not in c.get("flags", []):
                no_items_with_text.append(nm)
            if not has_text and n > 0:
                items_without_text.append(nm)
        rec(not no_items_with_text, "every government with expenditure text has at least one item (or a flag)",
            ", ".join(no_items_with_text[:8]))
        rec(not items_without_text, "no items invented for governments with no expenditure text",
            ", ".join(items_without_text[:8]))
        # amounts in the source: each $ figure in the 2025 text should surface as an item amount
        lost = []
        for nm, (r, c) in matched.items():
            figs = re.findall(r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)", (r.get("2025 Expenditures") or "") + " " + (r.get("2022, 2023, 2024 expenditures") or ""))
            have = [x["amount"] for x in items if x.get("county_id") == c["id"] and is_num(x.get("amount"))]
            for fgs in figs:
                v = money(fgs)
                if v is not None and not any(abs(v - h) < 0.01 for h in have):
                    lost.append(f"{nm}: ${fgs}")
        if lost:
            warn("dollar figures in source text with no matching item amount",
                 f"{len(lost)}: " + "; ".join(lost[:6]))
        meta_n = meta.get("totals", {}).get("items") if isinstance(meta.get("totals"), dict) else None
        if meta_n is not None:
            rec(meta_n == len(items), "meta item count equals items.json length", f"meta {meta_n} vs {len(items)}")

        # flags
        for nm, (r, c) in matched.items():
            e = expected_for(r)
            t25 = e["text_2025"].strip().lower()
            if t25 in empty_markers and "no_expenditure_text" not in c.get("flags", []) and \
                    e["text_prior"].strip().lower() in empty_markers:
                warn("empty expenditure text without no_expenditure_text flag", nm)
                break

        # privacy and hygiene
        priv_hits = []
        try:
            pub = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "docs", "explorer"],
                                 capture_output=True, text=True, check=True).stdout.splitlines()
            scan = [root / f for f in pub]  # tracked or publishable (not gitignored)
        except Exception:  # noqa: BLE001
            scan = list((root / "docs").rglob("*")) + list((root / "explorer").rglob("*"))
        for p in scan:
            if p.is_file() and p.suffix.lower() in {".json", ".md", ".html", ".js", ".css", ".py", ".txt", ".yml", ".yaml", ".svg"} \
                    and p.name != "verify.py" and ".git" not in p.parts and p.name != ".verify-source.csv":
                try:
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for pat in PRIVATE_PATTERNS:
                    if re.search(pat, txt):
                        priv_hits.append(f"{p.relative_to(root)} ~ {pat}")
        rec(not priv_hits, "no private paths or key-like strings under docs/ or explorer/", "; ".join(priv_hits[:6]))

        csv_in_docs = [str(p.relative_to(root)) for p in (root / "docs").rglob("*") if p.is_file() and p.suffix.lower() in {".csv", ".tsv", ".xlsx"}]
        rec(not csv_in_docs, "no raw CSV/XLSX present under docs/", ", ".join(csv_in_docs))
        tracked, git_ok = [], True
        try:
            out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
            tracked = [f for f in out if f.lower().endswith((".csv", ".tsv", ".xlsx")) and (f.startswith("docs/") or f.startswith("explorer/"))]
            tracked += [f for f in out if f.startswith("research/")]
        except Exception:  # noqa: BLE001
            git_ok = False
        if git_ok:
            rec(not tracked, "no raw CSV or research/ file is tracked by git under docs/ or explorer/", ", ".join(tracked[:6]))
        else:
            warn("git ls-files unavailable", "tracked-file check skipped")
        wide = [c.get("report_url") for c in counties if c.get("report_url") and not str(c["report_url"]).startswith("https://")]
        rec(not wide, "report_url values are https URLs or null", ", ".join(map(str, wide[:3])))
        rec(isinstance(meta.get("caveats"), list) and len(meta["caveats"]) > 0, "meta.caveats is a non-empty list")
        rec(bool(meta.get("method_version")), "meta.method_version set", str(meta.get("method_version")))
        return report()
    finally:
        if tmp_created:
            try:
                csv_path.unlink()
            except OSError:
                pass


def report() -> int:
    w = max((len(n) for _, n, _ in results), default=10)
    print("Settlement explorer verification\n" + "=" * 32)
    for st, n, d in results:
        line = f"[{st}] {n}"
        if d and (st != "PASS" or len(d) < 80):
            line += f"\n       {d}"
        print(line)
    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print("\n%d checks, %d passed, %d failed, %d warnings"
          % (len([r for r in results if r[0] != "WARN"]),
             len([r for r in results if r[0] == "PASS"]), len(fails), len(warns)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
