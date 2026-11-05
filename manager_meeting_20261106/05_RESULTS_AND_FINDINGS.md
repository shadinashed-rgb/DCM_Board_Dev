# Results and findings

Run `development/runs/aligned_20261105_004`: core assessment 3 Nov 2026, CRR assessment 4 Nov 2026. Detail is in `attachments/reports/` (`REVIEW.md`, workbooks, owner-review files).

## Headline numbers

| Measure | Value |
|---|---:|
| Development records | 631 |
| Signal evidence (SIG01 8, SIG02 63) | 71 |
| Context records (utilisation 442, credit 118) | 560 |
| Test candidates (all SIG02) | 9 |
| Signals with no data yet | 5 (SIG03A, SIG03B, SIG04, SIG06, SIG07) |
| Owner questions to resolve | 44 |
| Confirmed business triggers | 0 |
| Automated tests | 87 pass |

## By client

| Client | Live signal | Notable evidence |
|---|---|---|
| **Vodafone** (MG001356) | SIG02: **7 facilities approved 17 Sep 2026**: RDS ×2 (USD 75m, EUR 75m), GIS12 USD 250m, STR USD 20m, plus three small lines (CCP, ECC, USC; 125–200k each) | Two Cat A REV sub-limits; no drawing increase. Utilisation context peak 94.3% (FGTE, EGP) |
| **Siemens Energy** (MG102229) | SIG02: **1 facility approved 6 Oct 2026** (FGL, AED 40m, UAE) | REV sub-limit without a Cat A link. Competing CRRs on one CIN (2.1 / 3.1 / N/A). Utilisation context 76.8% and 74.2% |
| **SoftBank** (MG101624) | SIG02: **1 facility approved 17 Sep 2026** (FCL, USD 400m proposed limit, created 9 Jul) | **USD 179.7m drawn on a Cat A term loan**, but no prior snapshot to measure a drawing. A USD 200m sub-limit is unchanged and has no product code. Two utilisation ratios at 100% |

## The best example to show

**SoftBank, facility `00010341075552511210201`.** Facilities records a new FCL facility with a USD 400m proposed limit: created 9 Jul 2026, approved by credit on 17 Sep 2026. The same ID appears in CLO as a Cat A term sub-limit with **USD 179.7m already drawn** in the 2 Nov snapshot. Independently, DRR shows a SoftBank FLNS exposure (DRR uid 995902483) with a **USD 400m limit and USD 179.7m utilised (44.9%)** on 2 Nov. These are the same amounts in a third source, matched on amounts only, not on IDs.

Together, these say "a new, large bank facility was approved and is substantially drawn." That is exactly the pattern Jerome described as a precursor to bond refinancing.

It is not a confirmed trigger yet. Three things are still needed:
1. the cross-source ID match must be validated
2. a prior snapshot is needed to measure the drawing
3. FX and participation are needed for the EUR 50m test

## Findings that matter for the discussion

1. **The definitions are now clear; the data is the constraint.** Five of seven signals have no usable source. That is the main practicality question.
2. **SIG01, the signal Jerome stressed most, is blocked by one field.** CLO's default drawn amount is blank on every row. A LoanIQ drawn amount by facility, the HSBC participation share and an FX rule would unlock it.
3. **The approval date is not the creation date.** They match for only 9 of 50 facilities, so the credit team must confirm which date marks the approval of a *new* facility. One SoftBank facility only becomes a candidate under the approval-date rule.
4. **Cat A is usable.** 85 of 105 Facilities rows are CAT-A, and 3 of 5 CLO sub-limits match a Facilities ID. That is enough to filter drawings once the match is validated.
5. **Utilisation is not covenant pressure.** Five high utilisation ratios exist, but Jerome's covenant pressure needs leverage against the covenant maximum, and no covenant tests are available.
6. **Entity matching works for three clients but is manual.** The CIN, GID and PVD identifiers differ by source. Scaling to dozens of clients needs a reviewed mapping, which is the biggest hidden effort.
7. **Data freshness varies.** CLO and DRR are 2 Nov, Facilities 2 Nov, PVD 30 Sep (stale), Application Ratings 3 Nov. Daily refresh is not possible from manual extracts.

## What changed from the previous version

| | development-1 | development-2 (meeting-aligned) |
|---|---|---|
| Records | 626 | 631: all 626 carried forward, plus 5 new SIG01 comparisons |
| SIG01 | 3 REV comparisons | 8: REV + TERM, two drawn fields, Cat A and EUR 50m test |
| SIG02 candidates | 8 (creation date) | 9 (approval date) |
| SIG06 | 442 utilisation rows | 0: utilisation moved to context; covenant rule ready |
| SIG07 | 118 category/CRR rows | 0: moved to context; source is call reports |
