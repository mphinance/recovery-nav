"""Build the static site into site/dist from data/build/facilities.json."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.fetch_dhs import LEVEL_LABELS  # noqa: E402
SITE = ROOT / "site"
DIST = SITE / "dist"


def main() -> None:
    site = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())
    facs = json.loads((ROOT / "data" / "build" / "facilities.json").read_text())
    env = Environment(loader=FileSystemLoader(SITE / "templates"), autoescape=select_autoescape(["html"]))
    levels = [(k, v) for k, v in LEVEL_LABELS.items() if k not in ("prevention", "dui_assessment")]
    counties = sorted({f["county"] for f in facs})

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "f").mkdir(parents=True)
    shutil.copytree(SITE / "static", DIST / "static")

    geo = {f["id"]: {"lat": f["geo"]["lat"], "lon": f["geo"]["lon"], "name": f["name"], "city": f["city"]}
           for f in facs if f.get("geo")}
    for f in facs:
        f["street"] = f["street"].title()
    ctx = dict(site=site, labels=LEVEL_LABELS)
    (DIST / "index.html").write_text(env.get_template("index.html").render(
        **ctx, title="Find care", root="", facilities=facs, counties=counties, levels=levels, geo=geo))
    for f in facs:
        peers_dir = ROOT / "data" / "peers" / f["id"]
        peers = []
        if peers_dir.exists():
            for p in sorted(peers_dir.glob("*.yaml")):
                d = yaml.safe_load(p.read_text()) or {}
                if d.get("note") and d.get("by"):
                    peers.append(d)
        (DIST / "f" / f"{f['id']}.html").write_text(env.get_template("facility.html").render(
            **ctx, title=f["name"], root="../", f=f, peers=peers))
    for name, title in (("calling", "Calling a facility"), ("method", "How this works")):
        body = (SITE / "pages" / f"{name}.html").read_text()
        (DIST / f"{name}.html").write_text(env.get_template("page.html").render(
            **ctx, title=title, root="", body=body))
    print(f"built {len(facs)} facility pages -> {DIST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
