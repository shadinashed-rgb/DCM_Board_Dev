#!/usr/bin/env python3
"""Restore the raw development inputs from the archived signal-workbook package.

Raw client exports are deliberately not committed to git (see .gitignore). They
ship inside signal_workbooks_20261105_003.zip at the repository root. This script
copies development/data/ (and the supporting sql/ samples) out of that archive,
verifying each file against the package's own PACKAGE_FILE_HASHES.json.

Usage (from development/):  python3 -B tools/extract_inputs.py [--zip ../signal_workbooks_20261105_003.zip]
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ('development/data/', 'development/sql/')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--zip', default=str(ROOT.parent / 'signal_workbooks_20261105_003.zip'))
    p.add_argument('--force', action='store_true', help='overwrite files that already exist')
    a = p.parse_args()
    archive = zipfile.ZipFile(a.zip)
    names = [n for n in archive.namelist() if not n.startswith('__MACOSX') and not n.endswith('/')]
    root = next(n.split('/')[0] for n in names if n.endswith('PACKAGE_FILE_HASHES.json'))
    hashes = json.loads(archive.read(f'{root}/PACKAGE_FILE_HASHES.json'))
    # PACKAGE_FILE_HASHES.json maps package-relative paths to SHA-256 digests.
    known = {k: v for k, v in hashes.items() if isinstance(v, str)}
    written = verified = skipped = 0
    for name in names:
        rel = name[len(root) + 1:]
        if not rel.startswith(PREFIXES) or Path(rel).name == '.DS_Store':
            continue
        target = ROOT / rel[len('development/'):]
        if target.exists() and not a.force:
            skipped += 1
            continue
        data = archive.read(name)
        if rel in known:
            if hashlib.sha256(data).hexdigest() != known[rel]:
                raise SystemExit(f'Hash mismatch for {rel}; archive is not the expected package')
            verified += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written += 1
    print(f'Extracted {written} files ({verified} hash-verified, {skipped} already present) into {ROOT}')


if __name__ == '__main__':
    main()
