# recovery-nav

**Live: [mphinance.github.io/recovery-nav](https://mphinance.github.io/recovery-nav/)**

Wisconsin is receiving more than $874 million from opioid lawsuits, and 70 percent of it goes to 87 local governments: 71 counties and 16 cities and villages. Each reports to the state what it received, what it paid out, and what it is sitting on. Those reports are scattered across PDFs. The **Wisconsin Opioid Settlement Explorer** puts them in one place, so you can see how much each government has received, how much it has spent, and what it says it is spending on. As of the December 31, 2025 reports: about $162.6 million received, $7.9 million in interest, $44.1 million paid out (26 percent), and $125.4 million still on hand.

This repo also holds an older, separate treatment-and-recovery guide for Southeast Wisconsin (see the last section).

## What you can do with it

- Look up your county or city: receipts, disbursements, interest, balance and percent spent, by year, 2022 to 2025.
- Rank and compare governments, for example who has spent the least of what they received.
- Read what each government says it funds, in its own words, sorted into categories (naloxone, peer recovery, treatment, courts, prevention, and so on).
- Follow every figure back to the filing the government submitted, where a link exists.
- Download the derived data as plain JSON (`docs/data/`) and build on it. Field meanings are in the [data dictionary](docs/data-dictionary.md).

## Where the numbers come from

- **Source:** the settlement tracker built by Wisconsin Watch from county and municipal reports to the state: [github.com/Wisconsin-Watch/2026_06_23_Opioid_Settlment_Find_Expense](https://github.com/Wisconsin-Watch/2026_06_23_Opioid_Settlment_Find_Expense), file `data/cleaned_data_all.csv`. Settlement background: [Wisconsin DHS opioid settlement funds](https://www.dhs.wisconsin.gov/opioids/settlement-funds.htm).
- **Licensing:** that repository has no license. So we do **not** redistribute their file. It is downloaded at build time into a git-ignored folder, and this repo publishes only derived totals and each government's own short phrases, with attribution.
- **Traceable:** every number belongs to one named government and one year. Where the source gives a filing link, it is on that government's record (`report_url`).
- **Window:** calendar years 2022 to 2025 for flows; balance as of December 31, 2025.
- **Caveats:** figures are self-reported by each government and have not been audited. A handful of balances do not reconcile with receipts minus disbursements; those are flagged, not fixed. Two misspelled names in the source are corrected and flagged. Full rules: [methodology](docs/methodology.md).

## How we check the numbers

Two scripts, written separately so one can catch the other's mistakes.

- `explorer/validate.py`: checks the published JSON for shape and internal consistency.
- `explorer/verify.py`: an independent checker built only from the schema and the source CSV. It recomputes statewide and per-government totals, balances, percent spent and item counts, then asserts the published JSON matches. It also tests that no null became a zero, that ids are unique, that every government in the CSV is present, that every category id is valid, that each item's text and amount trace to the county's own wording, and that no raw CSV or private path is tracked or published. It prints a report and exits non-zero on any failure.

## What this is not

- **Unofficial.** Not a state, county or Wisconsin Watch product. Not endorsed by anyone named in it.
- **County-reported.** If a county reported it wrong, the explorer shows it wrong, with a flag where we can detect it.
- **Initiatives are not cash spent.** The spending items are what governments say they fund or plan to fund. Only "disbursements" is money paid out. Item amounts do not add up to disbursements.
- **Categories are keyword labels,** not audits, and some will be wrong.
- **Not legal or financial advice.** Nothing here tells a government what it may or must spend on.

## Run it yourself

Python 3.10 or newer.

```
git clone https://github.com/mphinance/recovery-nav.git
cd recovery-nav
python3 -m venv .venv && .venv/bin/pip install pyyaml
.venv/bin/python explorer/build_data.py      # downloads the source CSV, writes docs/data/*.json
.venv/bin/python explorer/validate.py        # shape and consistency checks
.venv/bin/python explorer/verify.py          # independent recompute, exits 1 on any failure
python3 -m http.server -d docs 8000          # then open http://localhost:8000
```

`build_data.py --no-download` reuses the CSV already in `explorer/data/raw/`. `verify.py --csv PATH` points the checker at a specific copy of the source file. The site in `docs/` is static HTML, CSS and JavaScript served by GitHub Pages; there is no server and no build step beyond the data files.

**Layout:** `explorer/` data pipeline, schema (`SCHEMA.md`) and category rules (`categories.yaml`); `docs/` the site, its data, and the method notes.

**Contributing:** open an issue first for anything beyond a typo. Category rules are plain regular expressions in `explorer/categories.yaml`; improving them is the easiest useful contribution. Run `verify.py` before you open a pull request.

## Corrections

Spotted a wrong number, a bad category, or a stale filing? [Open an issue](https://github.com/mphinance/recovery-nav/issues). Give the government, the figure, what you expected, and a link to where the right number appears. Corrections to the underlying reports have to be made at the source (the government, or Wisconsin Watch); once their file changes, a rebuild picks it up.

## Why it matters

Settlement money is meant for treatment, prevention and recovery, and it arrives through 2038. As of the end of 2025, most of it is unspent. Residents, reporters and county boards can only ask good questions about that if the figures are easy to find and easy to check. This is a small public utility for that, built on public records, with the arithmetic shown.

## The older guide

`pipeline/`, `site/`, `config/` and `data/ratings/` hold a neutral guide to substance use treatment and recovery in Southeast Wisconsin: state license data from the Wisconsin Department of Health Services, plain-English levels of care, signed reviews, and a map. No referral fees, no paid placement, no health data collected. It is separate from the explorer. Build notes are in `AGENTS.md`.

## License

- **Code:** MIT, see `LICENSE`.
- **Data:** figures are public facts reported by Wisconsin governments and compiled by Wisconsin Watch; attribution is required and retained in `docs/data/meta.json`. The source file itself keeps its own (unlicensed) status and is not redistributed here.
- **Reviews, site text of the older guide, and the project name and brand:** all rights reserved, see `CONTENT-NOTICE.md`.
