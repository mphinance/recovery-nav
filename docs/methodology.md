# Methodology

How the Wisconsin Opioid Settlement Explorer turns a public spreadsheet into the numbers on the site. Method version: **1.0**. Back to the [explorer](index.html) or the [data dictionary](data-dictionary.md).

## What this is

An unofficial reading aid for the opioid settlement money that Wisconsin's local governments report to the state. It is not a state product, not an audit, and not a statement from any county.

## Source

One source feeds every number: the settlement tracker compiled by Wisconsin Watch from the annual reports counties and municipalities file with the state. Their published file is `cleaned_data_all.csv` in the repository [Wisconsin-Watch/2026_06_23_Opioid_Settlment_Find_Expense](https://github.com/Wisconsin-Watch/2026_06_23_Opioid_Settlment_Find_Expense).

- That repository carries no license, so this project **does not copy or redistribute the file**. The build script downloads it at build time into a git-ignored folder (`explorer/data/raw/`). What is published here is derived figures and the counties' own short phrases, each traceable to a named government and year.
- Each government's own filing is linked from its page (`report_url`) when the source provides one.
- The source's own checks are not ours. We recompute totals and compare them (see below).

## The 87 governments

Wisconsin Act 57 (2021) sends 70 percent of settlement money to local governments and 30 percent to the state Department of Health Services. The local share goes to **87 governments: 71 counties and 16 municipalities** (cities and villages that settled separately). Every one of the 87 is in the data. A government is typed `county` if its name ends in "County", otherwise `municipality`.

Two government names in the source contain obvious spelling errors ("Mantiwoc County", "Pleasant Prarie, village"). We correct them openly and mark the record with the flag `name_corrected_from_source`.

## The 2022 to 2025 window

Every government reports receipts, disbursements and interest for calendar years 2022, 2023, 2024 and 2025. Totals are the sum of those four years. The **balance** is the amount the government reported on hand on **December 31, 2025**. Nothing before 2022 or after 2025 is included.

## Definitions

| Term | Meaning |
| --- | --- |
| Receipts | Settlement money the government reported receiving in a year. Interest is **not** included. |
| Disbursements | Money the government reported actually paying out in a year. This is the only figure that means "spent". |
| Interest | Interest earned on the held funds, reported separately. |
| Balance | Reported cash on hand, December 31, 2025. |
| Percent spent | `disbursements_total / (receipts_total + interest_total)`, a number from 0 to 1. Recomputed by us from the four-year totals, so it can differ slightly from the source's own figure (flag `pct_spent_differs_from_source`). |
| Statewide totals | Plain sums over the 87 governments. Statewide percent spent is total disbursements over total receipts plus interest, not an average of percentages. |

Money values are plain US dollars. Cents are kept. A blank in the source is stored as `null`, never as 0; a real reported 0.00 stays 0.

### Why balance may not equal receipts plus interest minus disbursements

For most governments it does. For some it does not, because the government reported a figure that does not reconcile or the source applied a correction. Any gap over $1 gets the flag `balance_mismatch`. We show the reported balance, not a computed one, and we do not "fix" it.

## Spending items

The county text columns in the source ("2025 Expenditures" and "2022, 2023, 2024 expenditures") are free prose. We split that prose into **items**, one per described activity. Every item keeps the county's own words.

### Parsing rules

1. Placeholder text such as "None", "None reported", "Optional questions not submitted" or "Treatment" alone produces no items. A government with only placeholders gets the flag `no_expenditure_text`.
2. A parenthesised dollar amount, for example `Peer support ($150,000)`, creates a priced item: the phrase before the parenthesis is the text, the number is the amount.
3. The remaining sentences become unpriced items with `amount: null`.
4. Text is split on sentence boundaries. Where one sentence lists several programs separated by commas, it stays one item and is flagged `multi_item_text`.
5. Milwaukee County writes headers like "Spending between 2023 and 2025:". Those set the period label for the items that follow.
6. The `period_label` is the county's own range (`2025`, `2022-2024`, `2023-2025`, and so on). Items from the "2022, 2023, 2024" column default to `2022-2024`.
7. Unusual cases carry flags: `phrase_may_include_unpriced_items`, `period_or_amount_unclear`, `multiple_amounts_in_parens`, `no_description`.

The parser is regular expressions and is deliberately simple. It will split some things wrongly. It never invents text and never rewrites a number.

### What "reported initiative" means

Every item has `status: "reported_initiative"`. It means: **the government listed this as something it funds or plans to fund, in its own report.** It does not mean the money has been paid out, that the amount was spent in one year, or that the program is running. Reported disbursements are the cash figure; items are a description of what the county says it is doing. Item amounts do **not** sum to a government's disbursements, and many governments list only some of their spending.

Milwaukee County lists commitments for 2023 to 2025 and 2024 to 2026. The ranges overlap, so those amounts must not be added together (flag `program_commitment_overlapping_periods`).

## Categories and the keyword rules

Each item gets exactly one category. The categories and their patterns live in a plain file, `explorer/categories.yaml`, so anyone can read and change them.

- Rules are case-insensitive regular expressions tested against the item text.
- Categories are tested **in the order they appear in the file**. The **first** category with any matching pattern wins. This is why, for example, jail medication rules come before general treatment.
- If nothing matches, the item is `other`.
- For an item flagged `phrase_may_include_unpriced_items`, only the last comma-separated chunk is classified.

The 15 categories: `jail_moud`, `treatment_residential`, `treatment_outpatient`, `peer_recovery`, `diversion_courts`, `reentry`, `harm_reduction_naloxone`, `prevention_education`, `navigation_case_management`, `housing_recovery`, `enforcement`, `medical_examiner_epi`, `data_analytics`, `staff_admin`, `other`. Labels and descriptions are in the [data dictionary](data-dictionary.md).

Categories are a keyword label, not an audit. Expect individual mistakes. The share landing in `other` is visible in the explorer.

## How the numbers are checked

1. **Build-time recomputation.** `explorer/build_data.py` recomputes every total, percent spent and balance gap from the raw per-year columns.
2. **Independent verifier.** `explorer/verify.py` was written separately from the schema and the source file only. It recomputes statewide and per-government totals, compares them to the published JSON, and checks nulls, duplicates, ids, categories, schema shape, item provenance, and that no raw file or private path is published. It exits non-zero on any failure.
3. **Validator.** `explorer/validate.py` checks the shape of the published files.

## Known limits

- Self-reported by each government, compiled by a news organization, not audited by anyone.
- Reports come in different formats; a few governments gave little detail.
- Item parsing and categories are heuristic.
- "Percent spent" is a snapshot of cash paid out against cash received. A low number can mean money is committed or contracted but not yet paid; it can also mean it is sitting.
- Settlement money continues to arrive through 2038, so receipts will keep growing.
- If a government files a correction, the next build picks it up only after the source is updated.

## Versioning

`method_version` in `docs/data/meta.json` identifies the rules in force. Change the version whenever parsing, category rules, the percent-spent formula or the window change. Each build also records `generated_at` and, per source, `retrieved_at`.

Found an error? Open an issue on the project's GitHub page and include the government, the figure, and where you saw the correct one.
