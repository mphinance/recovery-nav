# Data dictionary

Field-by-field description of the four files in `docs/data/`. Schema version 1. See also the [methodology](methodology.md) and the [explorer](index.html).

Conventions: dollar amounts are plain JSON numbers in US dollars, no strings and no commas. A missing value is `null`. It is never turned into 0. A real reported zero stays 0. Text is the government's own public wording. No personal data is included.

## counties.json

An array with one object per local government (87: 71 counties and 16 municipalities).

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Lowercase slug of the name, unique. Example: `washington-county`. |
| `name` | string | Government name, with source typos corrected (see `flags`). |
| `type` | string | `county` or `municipality`. |
| `receipts_total` | number | Sum of settlement receipts, 2022 to 2025. Excludes interest. |
| `disbursements_total` | number | Sum of money reported paid out, 2022 to 2025. |
| `interest_total` | number | Sum of interest earned, 2022 to 2025. |
| `balance_dec_2025` | number or null | Reported balance on December 31, 2025. |
| `pct_spent` | number or null | `disbursements_total / (receipts_total + interest_total)`, 0 to 1, six decimals. |
| `by_year` | object | Keys `"2022"` to `"2025"`; each holds `receipts`, `disbursements`, `interest` (number or null). |
| `report_url` | string or null | Link to the government's filing, when the source provides one. |
| `source` | string | Source name. |
| `source_notes` | string or null | Notes attached to the record in the source (for example, a correction received from the county). |
| `flags` | array of strings | Data-quality notes, listed below. |

### Government flags

| Flag | Meaning |
| --- | --- |
| `balance_mismatch` | Receipts plus interest minus disbursements differs from the reported balance by more than $1. |
| `no_expenditure_text` | The government gave no usable description of spending. |
| `no_interest_reported` | Interest is 0 in all four years. It may be unreported rather than none. |
| `pct_spent_differs_from_source` | Our percent spent differs from the source's by more than 0.05 points. |
| `name_corrected_from_source` | The name had an obvious spelling error that we fixed. |
| `initiatives_overlap_periods` | Items cover overlapping date ranges (Milwaukee County). |
| `missing_<year>_<field>` | A blank in the source, kept as null. |
| `missing_balance` | The balance cell was blank. |
| `report_url_not_documentcloud` | The linked filing is hosted somewhere other than DocumentCloud. |

## items.json

An array with one object per reported spending item parsed from a government's text.

| Field | Type | Meaning |
| --- | --- | --- |
| `county_id` | string | Matches `counties.json` `id`. |
| `county_name` | string | Government name. |
| `period_label` | string | The period as the government wrote it: `2025`, `2022-2024`, `2023-2025`, `2024-2026`. |
| `text` | string | The government's own phrase, trimmed. |
| `amount` | number or null | Dollar amount stated in the text. `null` when none was given. |
| `category` | string | A category `id` from `categories.json`. |
| `status` | string | Always `reported_initiative`: the government listed it. It is not proof the cash was spent. |
| `source` | string | Source name. |
| `flags` | array of strings | See below. |

### Item flags

`multi_item_text` (several programs in one phrase), `phrase_may_include_unpriced_items` (a priced phrase may have absorbed neighbours), `period_or_amount_unclear`, `multiple_amounts_in_parens`, `no_description`, `program_commitment_overlapping_periods` (Milwaukee County ranges overlap, do not add them).

## categories.json

An array of `id`, `label`, `description`. The rules that assign them are in `explorer/categories.yaml`; first match wins.

| id | Label |
| --- | --- |
| `jail_moud` | Jail-based medication for opioid use disorder |
| `treatment_residential` | Residential and inpatient treatment |
| `treatment_outpatient` | Outpatient treatment and counseling |
| `peer_recovery` | Peer and recovery support |
| `diversion_courts` | Diversion and treatment courts |
| `reentry` | Reentry |
| `harm_reduction_naloxone` | Harm reduction and naloxone |
| `prevention_education` | Prevention and education |
| `navigation_case_management` | Navigation, case management and crisis response |
| `housing_recovery` | Recovery and sober housing |
| `enforcement` | Law enforcement |
| `medical_examiner_epi` | Medical examiner and overdose death review |
| `data_analytics` | Data and analytics |
| `staff_admin` | Staffing, administration and responder wellness |
| `other` | Other or unclassified |

## meta.json

| Field | Meaning |
| --- | --- |
| `generated_at` | UTC time of the build. |
| `sources` | List of `name`, `url`, `retrieved_at`. |
| `totals` | `receipts`, `disbursements`, `interest`, `balance`, `governments`: statewide sums over the 87. |
| `caveats` | Plain-sentence limits, shown on the site. |
| `method_version` | Version of the rules in [methodology](methodology.md). |

## Reading the data

```
fetch("data/counties.json").then(r => r.json())
```

Join `items.json` to `counties.json` on `county_id` = `id`. To total a category, sum `amount` over items with that category, ignoring nulls, and say plainly that these are reported initiatives and not disbursements.
