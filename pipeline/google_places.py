"""Google Places (New) enrichment: rating, count and up to 5 reviews per facility.

ToS posture: official API only (no Maps scraping), keep Google attribution and
reviewer names as returned, persist only place_id long-term; review text is
cache-only and expires after 30 days. The API key is read from the environment
(or .env) and is never printed or logged.

Usage: python -m pipeline.google_places --names "exodus,manor,nova" [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

import requests
import yaml

LOG = logging.getLogger("google_places")
ROOT = Path(__file__).resolve().parent.parent
FAC = ROOT / "data" / "build" / "dhs_facilities.json"
IDS = ROOT / "data" / "places_ids.yaml"
CACHE = ROOT / "data" / "cache" / "places.json"
SEARCH = "https://places.googleapis.com/v1/places:searchText"
DETAIL = "https://places.googleapis.com/v1/places/{pid}"
TTL = 30 * 86400
MAX_CALLS = int(os.environ.get("PLACES_MAX_CALLS", "300"))


def load_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("GOOGLE_MAPS_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("GOOGLE_MAPS_API_KEY missing (env or .env)")
    return key


def call(session: requests.Session, method: str, url: str, mask: str, body: dict | None = None) -> dict:
    headers = {"X-Goog-FieldMask": mask}
    r = session.request(method, url, headers=headers, json=body, timeout=30)
    if r.status_code >= 400:
        # Never echo the request (it carries the key header); report status and API message only.
        msg = ""
        try:
            msg = r.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        raise RuntimeError(f"HTTP {r.status_code}: {msg[:200]}")
    return r.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="", help="comma list of name substrings; empty = all")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    facs = json.loads(FAC.read_text())
    wanted = [n.strip().lower() for n in args.names.split(",") if n.strip()]
    if wanted:
        facs = [f for f in facs if any(w in f["name"].lower() for w in wanted)]
    ids = yaml.safe_load(IDS.read_text()) if IDS.exists() else {}
    ids = ids or {}
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    need_search = sum(1 for f in facs if f["id"] not in ids)
    est = need_search + len(facs)
    LOG.info("facilities: %d | searches needed: %d | detail calls: %d | total calls: %d (cap %d)",
             len(facs), need_search, len(facs), est, MAX_CALLS)
    if args.dry_run:
        return
    if est > MAX_CALLS:
        raise SystemExit(f"estimated {est} calls exceeds cap {MAX_CALLS}; raise PLACES_MAX_CALLS deliberately")

    s = requests.Session()
    s.headers["X-Goog-Api-Key"] = load_key()
    now = time.time()
    skipped = False
    for f in facs:
        if skipped:
            break
        fid = f["id"]
        entry = ids.get(fid) or {}
        pid = entry.get("place_id")
        if not pid:
            q = f"{f['name']} {f['street']} {f['city']} WI {f['zip']}"
            try:
                res = call(s, "POST", SEARCH, "places.id,places.displayName,places.formattedAddress",
                           {"textQuery": q, "maxResultCount": 1})
            except RuntimeError as exc:
                if "HTTP 403" in str(exc):
                    LOG.warning("Places API denied (%s). Skipping enrichment; build continues with Maps links only.", exc)
                    skipped = True
                    break
                raise
            hit = (res.get("places") or [None])[0]
            if not hit:
                LOG.info("NO MATCH  %s", f["name"])
                continue
            pid = hit["id"]
            ids[fid] = {"place_id": pid, "matched_name": hit["displayName"]["text"],
                        "matched_address": hit.get("formattedAddress"), "verified": False}
        det = call(s, "GET", DETAIL.format(pid=pid),
                   "id,displayName,rating,userRatingCount,reviews,googleMapsUri")
        cache[fid] = {"fetched_at": now, "data": det}
        revs = det.get("reviews") or []
        LOG.info("%-45s -> %s | %s* (%s) | %d reviews returned",
                 f["name"][:45], ids[fid]["matched_name"][:35], det.get("rating"),
                 det.get("userRatingCount"), len(revs))

    cache = {k: v for k, v in cache.items() if now - v["fetched_at"] < TTL}
    IDS.parent.mkdir(parents=True, exist_ok=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    IDS.write_text(yaml.safe_dump(ids, sort_keys=True))
    CACHE.write_text(json.dumps(cache))


if __name__ == "__main__":
    main()
