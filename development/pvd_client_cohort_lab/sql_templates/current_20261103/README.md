# Current extraction pack

Generated as of 2026-11-03; source search window 2026-07-06 to 2026-11-03. Change the
as-of date by regenerating with refresh.py sql. These queries have not run in Starburst.

Run each source's schema statements separately, then its extract SQL, manually.
Save the result under the filename in extraction_plan.csv, keep CSV headers even
when empty, and transfer all data CSVs into starburst_exports/round_005 inside the
package. Keep schema/error/profile downloads outside that data folder.

Counterparty now uses delta.prod_party_gda.counterparty_core. The schema query
checks live access and column names. The extraction includes target mastergroups
OR observed CIN/GID routes so contradictory group mappings remain visible.

CLO retains the latest two available group snapshots for SIG01 comparisons.
Other sources retain one latest available snapshot per explicit group (or the
whole cohort export when no verified group field exists). Counterparty also keeps
snapshots preceding CLO dates for point-in-time enrichment. An absent current
facility is not resurrected from its last historical row. All columns are retained
for this testing round; date/version reduction controls the main row expansion.

Facilities uses record_start_dt/record_end_dt, including open end 99991231;
overlapping versions remain for conflict checks. This rule requires source-owner
validation. latest_record=CURRENT is not used because it would drop valid-looking
rows in the supplied sample. DRR borrower associations and parent/child limits are
preserved; no financial totals or arbitrary ROW_NUMBER deduplication are applied.

PVD remains at its native relationship/key grain. No facility identity is inferred
from joi_key. Covenant relationship lookups, if present, are candidate discovery
only; a verified source-scoped bridge is needed before covenant signal assignment.
Latest available is not a guarantee of current or complete coverage. If a source is
empty, inspect its date_coverage query before widening the window.
