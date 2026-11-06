# Settlement explorer data schema (v1)

> **Additions by the data pipeline (v1.1, additive only; no field renamed):** counties.json adds `source_notes` (the tracker's note, or null). items.json adds `county_name` and `flags` (array). Flags used: counties: balance_mismatch, interest_excluded, balance_timing_note, no_interest_reported, no_expenditure_text, initiatives_overlap_periods, name_corrected_from_source, pct_spent_differs_from_source, missing_<year>_<field>; items: program_commitment_overlapping_periods, phrase_may_include_unpriced_items, multi_item_text, amount_without_dollar_sign, period_or_amount_unclear. meta.totals adds `interest`. Items include unpriced phrases (amount null). Item `period_label` is "2025", "2022-2024", or the county's own range ("2023-2025", "2024-2026" for Milwaukee County).


Owner of `docs/data/*.json`: the data pipeline (`explorer/`). The site in `docs/` only reads them.
All dollar amounts are plain numbers in US dollars (no strings, no commas). Missing = null, never 0 unless the source says 0.

## docs/data/counties.json
Array of objects, one per local government (71 counties plus 16 municipalities):
- id (slug, e.g. "washington-county"), name, type ("county" | "municipality")
- receipts_total, disbursements_total, interest_total (2022 to 2025, summed)
- balance_dec_2025 (reported), pct_spent (disbursements_total / (receipts_total + interest_total), 0 to 1, computed by us and compared to the source figure)
- by_year: { "2022": {receipts, disbursements, interest}, "2023": ..., "2024": ..., "2025": ... }
- report_url (the county's filing if the source provides one), source ("Wisconsin Watch tracker" etc.)
- flags: array of strings (for example "balance_mismatch", "no_expenditure_text", "interest_excluded")

## docs/data/items.json
Array, one per reported spending line item parsed from county text:
- county_id, period_label (as the county wrote it, e.g. "2023-2025", "2025", "planned"), text (the original phrase, trimmed), amount (number or null), category (id from categories.json), status ("reported_initiative"; we do NOT claim this is cash disbursed unless the source says so), source

## docs/data/categories.json
Array: id, label, description. Starter set: jail_moud, treatment_residential, treatment_outpatient, peer_recovery, diversion_courts, reentry, harm_reduction_naloxone, prevention_education, navigation_case_management, housing_recovery, enforcement, medical_examiner_epi, data_analytics, staff_admin, other.

## docs/data/meta.json
generated_at, sources (list with name, url, retrieved_at), totals {receipts, disbursements, balance, governments}, caveats (list of plain sentences), method_version.

Rules: no personal data; text is the county's own public wording; every number traceable to a source and a year.
