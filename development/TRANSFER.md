# Move the workspace to another machine

The simplest route is to copy this complete folder and open it as the new IDE project. Start the new chat with NEW_CHAT_PROMPT.md. No original-machine path or global skill installation is required for the supported local workflow.

For transfer as a file, the handover is also packaged beside this folder as:

- bond_radar_workspace_20261104.zip
- bond_radar_workspace_20261104.zip.base64
- bond_radar_workspace_20261104.sha256 (hashes of both transfer files)

These archives deliberately contain the real client exports and historical evidence, not just synthetic demo data.

If transferring the Base64 file, run in its download folder:

```sh
python3 -c "import base64,pathlib; p=pathlib.Path('bond_radar_workspace_20261104.zip.base64'); p.with_suffix('').write_bytes(base64.b64decode(p.read_bytes()))"
python3 -m zipfile -t bond_radar_workspace_20261104.zip
python3 -m zipfile -e bond_radar_workspace_20261104.zip unpacked_handover
cd unpacked_handover/bond_radar_workspace_20261104
python3 -B verify_workspace.py
```

Extract to a new empty location; do not overwrite another working development copy. On Windows use `py -3` if required. The ZIP has one top-level workspace folder. Once extracted, use START_HERE.md; the Base64 file is only a transport encoding, not something to feed into the data pipeline.

MANIFEST.json checks every tracked shipped file by byte count and SHA256. Additional new files/runs are ignored. Intentional edits invalidate the original snapshot checksum for those files, which is expected: preserve the manifest as the original receipt. New development should have its own version history and raw-export manifests. The internal catalogue can be regenerated with `python3 -B tools/catalog_data.py` after reviewing new data, but doing so changes the tracked snapshot catalogue.
