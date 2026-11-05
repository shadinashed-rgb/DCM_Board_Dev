# CSV input area

Start with `pvd.csv`, exported from the PVD discovery SQL after schema/date checks. Later add `clo.csv`, `drr.csv`, `counterparty.csv`, `facilities.csv`, `kyc.csv` and `covenants.csv` as their verified identifier routes become available.

For multiple exports per source use a subfolder such as `pvd/part-001.csv`. Keep the same header order within a source and do not keep a flat source CSV alongside its chunk folder. Metadata sidecars use the same stem, such as `part-001.metadata.json`. Put schema/profile/DDL/query exports in separate `schemas/` or `queries/` folders, never among data chunks.

`approved_identifiers.csv` is intentionally header-only. Copy the first analysis's `identifier_review.csv` here, then record reviewed decisions/evidence. Keep the file in the next iteration with `--approved`; new proposals remain pending and prior/manual decisions are retained. The program never edits this input file.

Use actual SQL-client exports with original headers, UTF-8, correct CSV quoting and text identifiers. Source files are read-only inputs. Missing files are reported as unavailable; they are not replaced by made-up data.
