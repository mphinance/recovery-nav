"""Merge DHS facilities + geocodes + human ratings + (optional) Google Places cache.

Output: data/build/facilities.json. A facility is `reviewed` only when its rating
file has a non-empty verdict AND a disclosure. Every facility gets a plain Google
Maps search link (no API) so visitors can read Google reviews directly.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import quote_plus

import yaml

LOG = logging.getLogger("build_dataset")
ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"


def maps_link(f: dict) -> str:
    q = f"{f['name']} {f['street']} {f['city']} WI {f['zip']}"
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(q)}"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    facs = json.loads((D / "build" / "dhs_facilities.json").read_text())
    geo = json.loads((D / "cache" / "geocode.json").read_text()) if (D / "cache" / "geocode.json").exists() else {}
    places = json.loads((D / "cache" / "places.json").read_text()) if (D / "cache" / "places.json").exists() else {}
    ratings: dict[str, dict] = {}
    for p in (D / "ratings").glob("*.yaml"):
        r = yaml.safe_load(p.read_text()) or {}
        if r.get("facility_id"):
            ratings[r["facility_id"]] = r

    reviewed = incomplete = 0
    for f in facs:
        f["geo"] = geo.get(f["id"])
        f["google_maps_url"] = maps_link(f)
        g = (places.get(f["id"]) or {}).get("data")
        f["google"] = ({"rating": g.get("rating"), "count": g.get("userRatingCount"),
                        "reviews": g.get("reviews", [])[:5], "uri": g.get("googleMapsUri")} if g else None)
        r = ratings.get(f["id"])
        if r and r.get("verdict") and r.get("disclosure"):
            f["review"] = r
            reviewed += 1
        else:
            f["review"] = None
            if r:
                incomplete += 1
    out = D / "build" / "facilities.json"
    out.write_text(json.dumps(facs, indent=2))
    LOG.info("facilities %d | reviewed %d | rating files incomplete (need verdict+disclosure) %d | google %d -> %s",
             len(facs), reviewed, incomplete, sum(1 for f in facs if f["google"]), out.relative_to(ROOT))


if __name__ == "__main__":
    main()
