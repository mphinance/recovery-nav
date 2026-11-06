#!/usr/bin/env python3
"""Refresh docs/district12.html from the Greater Milwaukee Central Office directory.

Makes ONE request per run. If the source is down, changes shape, or returns zero
meetings, the existing page is left untouched and the script exits 0 so the
scheduled workflow never commits an empty page.
"""
import html
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.aamilwaukee.com/index.php?page=meeting-directory"
USER_AGENT = (
    "recovery-nav-district12/1.0 (+https://github.com/mphinance/recovery-nav; "
    "weekly list refresh, one request per run)"
)
TARGET_FILE = Path(__file__).resolve().parent.parent / "docs" / "district12.html"
MIN_MEETINGS = 1

CODE_MAP = {
    "handicap access": "handicap",
    "ladies/women": "womens",
    "men's": "mens",
    "ns": "ns",
    "non-smoking": "ns",
    "beginner's class": "beginner",
    "online meeting available": "online",
    "weekly/monthly open meeting": "open",
}


def clean(text):
    """Normalize rendered text: no em or en dashes."""
    return (text or "").replace("—", ", ").replace("–", "-")


def fetch_meetings():
    try:
        r = requests.post(
            SOURCE_URL,
            data={"district": "12", "submit": "Search"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Source unavailable, leaving page unchanged: {e}")
        return None


def parse_meetings(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    meetings = []
    for table in soup.find_all("table", border="0"):
        try:
            m = {"name": "", "day": "", "time": "", "codes": [], "notes": "",
                 "address_lines": [], "google_maps_link": "", "additional_info": ""}
            rows = table.find_all("tr")
            if not rows:
                continue
            tds = rows[0].find_all("td")
            if len(tds) < 3:
                continue
            left = tds[0]
            name_span = left.find("span", style=lambda s: s and "font-size: 25px" in s)
            if name_span:
                m["name"] = name_span.get_text(strip=True)
            dt_span = left.find("span", style=lambda s: s and "font-weight: bolder" in s)
            if dt_span:
                dt = dt_span.get_text(strip=True)
                if " - " in dt:
                    m["day"], m["time"] = dt.split(" - ", 1)
                else:
                    m["day"] = dt
            for br in left.find_all("br"):
                nxt = br.next_sibling
                if nxt and isinstance(nxt, str):
                    t = nxt.strip()
                    if t.startswith("Codes:"):
                        m["codes"] = [c.strip() for c in t.replace("Codes:", "").split(",")]
                    elif t.startswith("Notes:"):
                        m["notes"] = t.replace("Notes:", "").strip()
            right = tds[2]
            loc = right.find("strong", string=re.compile("Location:"))
            if loc:
                cur = loc.next_sibling
                while cur:
                    if cur.name == "a":
                        break
                    if isinstance(cur, str):
                        part = cur.strip()
                        if part and not part.startswith(("District", "Group", "County")):
                            m["address_lines"].append(part)
                    cur = cur.next_sibling
            link = right.find("a", href=re.compile("maps.google.com"))
            if link:
                m["google_maps_link"] = link["href"]
            if len(rows) > 1:
                info = rows[1].find("td", colspan="3")
                if info:
                    m["additional_info"] = info.get_text(" ", strip=True).replace(
                        "Additional Meeting Information:", "").strip()
            if m["name"]:
                meetings.append(m)
        except Exception as e:
            print(f"Skipped one unparsable meeting block: {e}")
    return meetings


def card(m):
    e = lambda v: html.escape(clean(v), quote=True)
    tags = []
    for code in m["codes"]:
        slug = CODE_MAP.get(code.lower())
        if slug:
            tags.append(slug)
    blob = (m["name"] + " " + m["notes"] + " " + m["additional_info"]).lower()
    if "women" in blob and "womens" not in tags: tags.append("womens")
    if "men" in blob and "mens" not in tags: tags.append("mens")
    if "handicap" in blob and "handicap" not in tags: tags.append("handicap")
    if "open" in blob and "open" not in tags:
        tags.append("open")
    elif "closed" not in tags and "open" not in tags:
        tags.append("closed")
    types = " ".join(sorted(set(tags)))
    search = f"{m['name']} {m['day']} {m['time']} {' '.join(m['address_lines'])} {m['notes']} {m['additional_info']}".lower()
    tag_html = ""
    for t in tags:
        label = {"mens": "Men's", "womens": "Women's"}.get(t, t.capitalize())
        tag_html += f'<span class="tag tag-{t}">{label}</span>'
    addr = "<br>".join(e(a) for a in m["address_lines"])
    maps = m["google_maps_link"]
    if "maps.google.com" not in maps:
        maps = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(" ".join(m["address_lines"]))
    notes = f"<div class='detail-item'><span class='detail-label'>Notes</span><p class='detail-value'>{e(m['notes'])}</p></div>" if m["notes"] else ""
    info = f"<div class='detail-item'><span class='detail-label'>Additional Info</span><p class='detail-value info-box'>{e(m['additional_info'])}</p></div>" if m["additional_info"] else ""
    return f"""
        <div class="meeting-card" data-day="{e(m['day'].lower())}" data-types="{types}" data-search="{e(search)}">
            <div class="meeting-header">
                <h3 class="meeting-name">{e(m['name'])}</h3>
                <div class="meeting-time">
                    <span class="day-badge">{e(m['day'])}</span>
                    <span class="time-value">{e(m['time'])}</span>
                </div>
            </div>
            <div class="meeting-details">
                <div class="detail-item">
                    <span class="detail-label">Location</span>
                    <p class="detail-value">{addr}</p>
                </div>
                {notes}
                {info}
            </div>
            <div class="meeting-footer">
                <div class="tags-container">
                    {tag_html}
                </div>
                <a href="{html.escape(maps, quote=True)}" target="_blank" rel="noopener" class="map-link">
                    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    Maps
                </a>
            </div>
        </div>
    """


def update_page(cards_html):
    if not TARGET_FILE.exists():
        print(f"Target page not found: {TARGET_FILE}")
        return False
    page = TARGET_FILE.read_text(encoding="utf-8")
    for marker in ("<!-- MEETINGS START -->", "<!-- MEETINGS END -->",
                   "<!-- UPDATED START -->", "<!-- UPDATED END -->"):
        if marker not in page:
            print(f"Marker missing from page: {marker}")
            return False
    page = re.sub(r"<!-- MEETINGS START -->.*?<!-- MEETINGS END -->",
                  lambda _: f"<!-- MEETINGS START -->\n{cards_html}\n        <!-- MEETINGS END -->",
                  page, flags=re.DOTALL)
    today = datetime.now(timezone.utc).strftime("%B %d, %Y").replace(" 0", " ")
    page = re.sub(r"<!-- UPDATED START -->.*?<!-- UPDATED END -->",
                  lambda _: f"<!-- UPDATED START -->List updated {today}<!-- UPDATED END -->",
                  page, flags=re.DOTALL)
    TARGET_FILE.write_text(page, encoding="utf-8")
    return True


def main():
    raw = fetch_meetings()
    if not raw:
        return 0
    meetings = parse_meetings(raw)
    print(f"Parsed {len(meetings)} meetings.")
    if len(meetings) < MIN_MEETINGS:
        print("Zero meetings parsed (site structure may have changed). Page left unchanged.")
        return 0
    if update_page("".join(card(m) for m in meetings)):
        print(f"Updated {TARGET_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
