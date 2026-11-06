"""Fetch and normalize the Wisconsin DHS substance-use provider directory.

Source: https://www.dhs.wisconsin.gov/regulations/su/su-only-excel-directory.xlsx
Layout: row 1 = 17 descriptive headers, row 2 = service names for columns 18+,
data from row 3. A license appears once per effective-date window, so we keep
only the newest row per license.

Privacy: the file carries an emergency-contact person's name and facility email
addresses. Neither is written to the output.

Usage: python -m pipeline.fetch_dhs [--no-download]
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import openpyxl
import requests
import yaml

LOG = logging.getLogger("fetch_dhs")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "su-directory.xlsx"
OUT = ROOT / "data" / "build" / "dhs_facilities.json"
REGION = ROOT / "config" / "region.yaml"
URL = "https://www.dhs.wisconsin.gov/regulations/su/su-only-excel-directory.xlsx"
UA = "recovery-nav/0.1 (+contact: project owner; weekly build)"

# DHS 75.x service code -> plain-English level of care
LEVELS: dict[str, str] = {
    "75.57": "withdrawal_management",
    "75.58": "withdrawal_management",
    "75.55": "inpatient_hospital",
    "75.54": "residential",
    "75.56": "residential",
    "75.53": "transitional_residential",
    "75.52": "day_treatment",
    "75.51": "intensive_outpatient",
    "75.49": "outpatient",
    "75.50": "outpatient",
    "75.59": "medication_treatment",
    "75.60": "medication_treatment",
    "75.15": "dui_assessment",
    "75.14": "prevention",
}
LEVEL_LABELS = {
    "withdrawal_management": "Detox / withdrawal management",
    "inpatient_hospital": "Hospital inpatient",
    "residential": "Residential treatment",
    "transitional_residential": "Transitional living / step-down",
    "day_treatment": "Day treatment / partial hospitalization",
    "intensive_outpatient": "Intensive outpatient (IOP)",
    "outpatient": "Outpatient",
    "medication_treatment": "Medication treatment (methadone, buprenorphine, etc.)",
    "dui_assessment": "OWI / intoxicated-driver assessment",
    "prevention": "Prevention",
}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_date(value) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), "%m/%d/%Y")
    except (TypeError, ValueError):
        return datetime.min


def download() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(URL, headers={"User-Agent": UA}, timeout=60)
    resp.raise_for_status()
    RAW.write_bytes(resp.content)
    LOG.info("downloaded %d bytes", len(resp.content))


def load_rows() -> list[dict]:
    wb = openpyxl.load_workbook(RAW, read_only=True, data_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    headers = list(rows[0][:17])
    service_names = list(rows[1][17:])
    out: list[dict] = []
    for r in rows[2:]:
        if not any(r[:17]):
            continue
        rec = dict(zip(headers, r[:17]))
        flags = r[17:]
        rec["services"] = [n for n, f in zip(service_names, flags) if f in (1, "1", True)]
        out.append(rec)
    LOG.info("loaded %d raw rows", len(out))
    return out


def collapse(rows: list[dict]) -> list[dict]:
    """Newest effective-date row per license number."""
    best: dict[str, dict] = {}
    for rec in rows:
        key = str(rec.get("LICENSE") or rec.get("NAME"))
        cur = best.get(key)
        if cur is None or parse_date(rec["EFFECTIVE DATE"]) >= parse_date(cur["EFFECTIVE DATE"]):
            best[key] = rec
    return list(best.values())


def normalize(rec: dict) -> dict:
    codes = [s.split(" ", 1)[0] for s in rec["services"]]
    levels = sorted({LEVELS[c] for c in codes if c in LEVELS})
    name = (rec.get("PROVIDER") or rec.get("NAME") or "").strip()
    return {
        "id": f"{slugify(name)}-{rec.get('LICENSE')}",
        "name": name,
        "legal_name": (rec.get("NAME") or "").strip(),
        "license": str(rec.get("LICENSE")),
        "status": rec.get("STATUS"),
        "county": (rec.get("COUNTY") or "").strip().title(),
        "street": (rec.get("STREET") or "").strip(),
        "city": (rec.get("CITY") or "").strip().title(),
        "state": rec.get("STATE"),
        "zip": str(rec.get("ZIP") or "")[:5],
        "phone": rec.get("TELEPHONE"),
        "license_effective": str(rec.get("EFFECTIVE DATE")),
        "license_expires": str(rec.get("EXPIRATION DATE")),
        "levels_of_care": levels,
        "services": rec["services"],
    }


def _norm_street(f: dict) -> tuple[str, str]:
    return re.sub(r"\W+", "", f["street"].lower()), f["zip"]


def merge_facilities(facs: list[dict]) -> list[dict]:
    """Union licenses that are the same physical/organizational facility."""
    cfg = yaml.safe_load((ROOT / "config" / "merges.yaml").read_text()) or {}
    parent = {f["license"]: f["license"] for f in facs}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        if a in parent and b in parent:
            parent[find(a)] = find(b)

    seen: dict[tuple, str] = {}
    for f in facs:
        for key in (("addr",) + _norm_street(f), ("phone", f["zip"], re.sub(r"\D", "", f["phone"] or ""))):
            if key[0] == "phone" and not key[2]:
                continue
            if key in seen:
                union(f["license"], seen[key])
            else:
                seen[key] = f["license"]
    for g in cfg.get("groups", []):
        lic = g["licenses"]
        for other in lic[1:]:
            union(lic[0], other)

    names = cfg.get("display_names", {})
    groups: dict[str, list[dict]] = {}
    for f in facs:
        groups.setdefault(find(f["license"]), []).append(f)

    primaries = {g["primary"]: g for g in cfg.get("groups", []) if "primary" in g}
    prim_over = set(cfg.get("primary_overrides", {}))
    merged = []
    for members in groups.values():
        lead = next((m for m in members if m["license"] in prim_over or m["license"] in primaries), members[0])
        out = dict(lead)
        out["licenses"] = sorted({m["license"] for m in members})
        out["levels_of_care"] = sorted({l for m in members for l in m["levels_of_care"]})
        out["services"] = sorted({s for m in members for s in m["services"]})
        out["other_sites"] = [
            {"street": m["street"], "city": m["city"], "zip": m["zip"], "county": m["county"]}
            for m in members if m is not lead and _norm_street(m) != _norm_street(lead)
        ]
        label = names.get(lead["license"]) or (primaries.get(lead["license"]) or {}).get("display_name")
        if label:
            out["name"] = label
        out["id"] = f"{slugify(out['name'])}-{out['license']}"
        merged.append(out)
    return sorted(merged, key=lambda x: (x["county"], x["name"].lower()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.no_download or not RAW.exists():
        download()

    facilities = [normalize(r) for r in collapse(load_rows())]
    # Only entries that offer at least one substance-use level of care
    facilities = [f for f in facilities if f["levels_of_care"]]
    facilities = merge_facilities(facilities)
    cfg = yaml.safe_load(REGION.read_text())
    counties = {c.title() for c in cfg["counties"]}
    allow = {a.lower() for a in cfg.get("always_include", [])}
    for f in facilities:
        f["in_region"] = f["county"] in counties
        f["notable_outside_region"] = (not f["in_region"]) and any(a in f["name"].lower() for a in allow)
    kept = [f for f in facilities if f["in_region"] or f["notable_outside_region"]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(kept, indent=2))
    LOG.info("unique licenses with SU levels: %d | kept (region + notable): %d -> %s",
             len(facilities), len(kept), OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
