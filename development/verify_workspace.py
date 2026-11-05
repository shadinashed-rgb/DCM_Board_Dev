#!/usr/bin/env python3
"""Verify tracked handover files against MANIFEST.json; new run outputs are ignored."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent


def main():
    manifest=json.loads((ROOT/'MANIFEST.json').read_text())
    errors=[]
    for record in manifest['files']:
        path=ROOT/record['path']
        if not path.is_file():errors.append('Missing: '+record['path']);continue
        if path.stat().st_size!=record['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            errors.append('Changed: '+record['path'])
    if errors:
        print('\n'.join(errors));return 1
    print(f"Verified {len(manifest['files'])} handover files. Additional development/run files were not checked.")
    return 0


if __name__=='__main__':sys.exit(main())
