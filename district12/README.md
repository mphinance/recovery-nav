# District 12 meetings page

A mobile-friendly, searchable list of District 12 (Washington County, WI) AA meetings, served at
https://mphinance.github.io/recovery-nav/district12.html

The page is unofficial and not affiliated with Alcoholics Anonymous. It is not indexed by search engines (`noindex`).

## Source and ownership

Meeting data comes from the Greater Milwaukee Central Office directory:
https://www.aamilwaukee.com/index.php?page=meeting-directory

The data belongs to the Central Office and to the individual groups. This project only reformats it. The maintainer should confirm with the Central Office before promoting the page widely.

## How it works

`scrape_district12.py` makes one POST (`district=12`) per run, with a User-Agent that identifies this project and a 30 second timeout. It rewrites the card block and the "List updated" date in `docs/district12.html`. If the source is down or returns zero meetings, it prints the reason, exits 0 and leaves the page alone.

`.github/workflows/update_district12.yml` runs it every Sunday at 05:00 UTC (or on demand) and commits only `docs/district12.html` when it changed.

## Run it

```
python -m venv .venv && . .venv/bin/activate
pip install -r district12/requirements.txt
python district12/scrape_district12.py
```
