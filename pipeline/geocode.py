"""Geocode facilities with the free US Census batch geocoder (no key). Cached by id."""
from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path

import requests

LOG = logging.getLogger("geocode")
ROOT = Path(__file__).resolve().parent.parent
FAC = ROOT / "data" / "build" / "dhs_facilities.json"
CACHE = ROOT / "data" / "cache" / "geocode.json"
URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    facs = json.loads(FAC.read_text())
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [f for f in facs if f["id"] not in cache]
    LOG.info("to geocode: %d (cached %d)", len(todo), len(cache))
    if todo:
        buf = io.StringIO()
        w = csv.writer(buf)
        for f in todo:
            w.writerow([f["id"], f["street"], f["city"], "WI", f["zip"]])
        r = requests.post(URL, files={"addressFile": ("a.csv", buf.getvalue())},
                          data={"benchmark": "Public_AR_Current"}, timeout=180)
        r.raise_for_status()
        for row in csv.reader(io.StringIO(r.text)):
            fid, matched = row[0], row[2] if len(row) > 2 else ""
            if matched == "Match" and len(row) > 5 and row[5]:
                lon, lat = row[5].split(",")
                cache[fid] = {"lat": float(lat), "lon": float(lon)}
            else:
                cache[fid] = None
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache))
    hits = sum(1 for f in facs if cache.get(f["id"]))
    LOG.info("geocoded %d/%d (%.0f%%)", hits, len(facs), 100 * hits / max(len(facs), 1))
    for f in facs:
        if not cache.get(f["id"]):
            LOG.info("  MISS: %s | %s %s", f["name"], f["street"], f["city"])


if __name__ == "__main__":
    main()
