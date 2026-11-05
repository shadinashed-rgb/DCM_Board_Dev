# Bundled local signal engine

These runtime files and tests were copied from this project's `local_signal_lab` on 30 October 2026 so the new PVD cohort package can run independently. The earlier folder is unchanged. This is the local development/testing engine created for Bond Radar; it is not the historical CLO production handover solution.

Use the main `cohort.py run-signals` command for cohort filtering and group coverage. The bundled `config.json` leaves real business definitions unverified. It does not infer a PVD currency, a CIN from a composite key, a ratings-advisory event, or cross-source facility equivalence.
