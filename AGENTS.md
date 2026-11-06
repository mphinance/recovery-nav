# AGENTS.md

Neutral, locally grounded treatment and recovery guide for Southeast Wisconsin. Static site built from public state license data plus signed, disclosed human reviews.

## Run it
```
python -m venv .venv && .venv/bin/pip install openpyxl pyyaml requests jinja2
.venv/bin/python -m pipeline.fetch_dhs      # DHS xlsx -> data/build/dhs_facilities.json (--no-download reuses data/raw)
.venv/bin/python -m pipeline.geocode        # US Census batch geocoder, cached, no key
.venv/bin/python -m pipeline.build_dataset  # merge -> data/build/facilities.json
.venv/bin/python site/build.py              # static site -> site/dist (run as a script; `-m site.build` shadows stdlib `site`)
```
Optional: `pipeline.google_places` adds Google rating data. It needs `GOOGLE_MAPS_API_KEY` in the environment or a gitignored `.env`, and an active Google Cloud billing account. Without them it logs a warning and the build continues with plain Google Maps links. Never print or commit the key. Hard cap of 300 API calls per run.

## Rules
- Collects no health information and no personal data about visitors. No accounts. No referral fees and no paid placement. Do not add ads or paid listings.
- A facility shows as "Reviewed" only when its `data/ratings/<id>.yaml` has both a verdict and a plain-language disclosure of any connection.
- Public copy: no em or en dashes; no claims of affiliation with or endorsement by any 12-step fellowship, treatment program or agency; no unverified phone numbers (the crisis bar carries 988 only).
- Contact details for reviewers or peers never go in this repo.
- Site is `noindex` until the owner decides to launch.

## Layout
`pipeline/` data steps, `config/` region and merge rules, `data/ratings/` signed reviews, `site/` templates, static assets and pages, `docs/` public notes.
