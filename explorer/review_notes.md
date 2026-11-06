## (f) Manual sanity-read of categories (after rule tuning)

Read the 15 largest priced items per category. Corrections made through categories.yaml and build_data.py, not by hand-editing data:
- "Sobriety and Treatment Assisted Recovery program in the county jail" was matched to jail MOUD; removed, because the text does not say medication is provided. It now sits in outpatient treatment.
- Phrases with 2+ commas or over 100 characters bundle several programs under one amount (Kenosha, Dunn, Oconto, Washington, Waushara). They are forced to `other` with flag `phrase_may_include_unpriced_items` instead of guessing.
- First-responder wellness, the Sheriff's educational app, and "Justice Point" screening were moved to staff_admin, prevention_education and diversion_courts by rule order.

Known weak spots, left as is and visible in the data:
- Milwaukee County "community grants ... underserved groups" ($4.8M, the largest item) is `other`; the text does not say what the grants fund.
- Wauwatosa lines ($16, $886, $2,034, $7,853) repeat state-category wording rather than programs; their categories are low confidence.
- "Harm reduction beds" and "harm reduction data analytics" (Milwaukee County) are filed under harm reduction by keyword; housing and data are defensible alternatives.
- Dunn "Arbor place for treatment" is residential only because the facility name is in the rules.
- Rule matching is by keyword; "treatment" alone falls to outpatient.
- Two Mount Pleasant and Sawyer items carry `period_or_amount_unclear` (a 2021 expense and "2023 disbursements not specified"); amounts are kept as written.
- Waukesha's last 2025 item has its amount without a dollar sign, "(114,352)"; parsed and flagged `amount_without_dollar_sign`.

## (g) Spot-check against primary filings

Not completed. Every `doc_link` in the source (87 of 87) is a DocumentCloud URL, and DocumentCloud returned HTTP 403 (bot protection) for the document page, the API and the PDF host from this environment, including the Dodge and Eau Claire filings that matter most. No filing numbers were guessed. Within the CSV, the source's own `checking math` column was compared with our recompute: it matches ours except where the source note or the cell explains the gap (see (a)). The primary-filing check still needs a human with a browser for at least Eau Claire, Dodge, Monroe, Rusk, Waukesha and Milwaukee County.
