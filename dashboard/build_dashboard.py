#!/usr/bin/env python3
"""Build the self-contained DCM Bond Radar signals dashboard.

Reads the signal workbook package (a folder or a zip), extracts every workbook
into one JSON payload and writes a single self-contained HTML file from
``template.html``. The HSBC logo is taken from the LAF sample board inside the
archived 003 package, so the asset is never re-encoded.

Usage (from the repository root):

    python3 dashboard/build_dashboard.py \
        --src signal_workbooks_20261105_004 \
        --logo-from signal_workbooks_20261105_003.zip \
        --out dashboard/dcm_signals_dashboard.html

The default package is the development-2 (meeting-aligned) one.

Requires Python 3.10+ and openpyxl.  No values are recomputed or re-based:
the dashboard shows the evidence exactly as saved in the workbooks.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import sys
import zipfile
from pathlib import Path

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required: pip install openpyxl")

HERE = Path(__file__).resolve().parent
# Workbooks in the development-2 package. SIG03 holds SIG03A and SIG03B.
WORKBOOKS = ["SIG01", "SIG02", "SIG03", "SIG04", "SIG06", "SIG07", "CTX_UTIL", "CTX_CREDIT"]
# Native client labels in the workbooks -> display names used on the board.
CLIENT_DISPLAY = {
    "VODAFONE": "Vodafone",
    "Siemens Energy": "Siemens Energy",
    "SOFTBANK": "SoftBank",
}


class Package:
    """Uniform file access over a zip archive or an extracted folder."""

    def __init__(self, src: Path):
        self.src = src
        self.zip = zipfile.ZipFile(src) if src.is_file() else None
        if self.zip:
            names = [n for n in self.zip.namelist() if not n.startswith("__MACOSX")]
            roots = {n.split("/")[0] for n in names if n.endswith("SIGNAL_OVERVIEW.xlsx")}
            self.root = sorted(roots)[0] if roots else ""
        else:
            self.root = ""

    def read(self, rel: str) -> bytes:
        if self.zip:
            return self.zip.read(f"{self.root}/{rel}" if self.root else rel)
        return (self.src / rel).read_bytes()

    def workbook(self, rel: str):
        return openpyxl.load_workbook(io.BytesIO(self.read(rel)), data_only=True, read_only=False)

    @property
    def name(self) -> str:
        return self.root or self.src.name


def clean(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        return s if s != "" else None
    return v


def read_sheet(ws):
    """Return {title, notes, header, rows} for a workbook sheet.

    The package lays every sheet out as: title lines, a blank row, a header row
    (>=3 populated cells), data rows, then optional single-cell note lines.
    """
    raw = [[clean(c) for c in r] for r in ws.iter_rows(values_only=True)]
    title, notes, header, rows = [], [], None, []
    for r in raw:
        vals = [v for v in r if v is not None]
        if header is None:
            if len(vals) >= 3:
                width = max(i for i, v in enumerate(r) if v is not None) + 1
                header = [str(h) if h is not None else f"col{i}" for i, h in enumerate(r[:width])]
            elif len(vals) == 1:
                title.append(str(vals[0]))
            elif len(vals) == 2:
                title.append(f"{vals[0]}: {vals[1]}")
            continue
        if not vals:
            continue
        if len(vals) == 1 and r[0] is not None:
            # a single-cell line below the table is an explanatory note
            notes.append(str(vals[0]))
            continue
        if r[0] == 'Total':
            continue  # summary total rows are formulas over the table, not data
        rows.append(dict(zip(header, r[: len(header)])))
    return {"title": title, "notes": notes, "header": header or [], "rows": rows}


def compact(rows):
    """Drop None values to keep the embedded payload small."""
    return [{k: v for k, v in r.items() if v is not None} for r in rows]


def extract(pkg: Package) -> dict:
    data: dict = {"signals": {}, "evidence": [], "detail": {}, "lineage": {}}

    ov = pkg.workbook("SIGNAL_OVERVIEW.xlsx")
    summary = read_sheet(ov["Summary"])
    data["overview"] = {
        "title": summary["title"],
        "notes": summary["notes"],
        "signals": compact(summary["rows"]),
        "client_summary": compact(read_sheet(ov["Client summary"])["rows"]),
        "definitions": compact(read_sheet(ov["Definitions"])["rows"]),
        "findings": compact(read_sheet(ov["Findings"])["rows"]),
        "source_inventory": compact(read_sheet(ov["Source inventory"])["rows"]),
    }

    for sig in WORKBOOKS:
        wb = pkg.workbook(f"{sig}.xlsx")
        s_sum = read_sheet(wb["Summary"])
        entry = {
            "id": sig,
            "title": s_sum["title"],
            "notes": s_sum["notes"],
            "clients": compact(s_sum["rows"]),
            "definitions": compact(read_sheet(wb["Definitions"])["rows"]),
            "findings": compact(read_sheet(wb["Findings"])["rows"]),
            "sources": compact(read_sheet(wb["Sources"])["rows"]),
            "owner_review": compact(read_sheet(wb["Owner review"])["rows"]) if "Owner review" in wb.sheetnames else [],
            "coverage": compact(read_sheet(wb["Coverage"])["rows"]) if "Coverage" in wb.sheetnames else [],
        }
        data["signals"][sig] = entry

        for r in read_sheet(wb["Signal data"])["rows"]:
            if not r.get("evidence_id"):
                continue
            r = {k: v for k, v in r.items() if v is not None}
            r.setdefault("signal_id", sig)
            data["evidence"].append(r)

        for r in read_sheet(wb["Evidence detail"])["rows"]:
            eid = r.get("evidence_id")
            if eid:
                data["detail"][eid] = {k: v for k, v in r.items() if v is not None}

        for r in read_sheet(wb["Lineage"])["rows"]:
            eid = r.get("Evidence ID")
            if eid:
                data["lineage"].setdefault(eid, []).append(
                    [r.get("CSV file"), r.get("CSV record"), r.get("Role"), r.get("Evidence observation date")]
                )

    # Package-level verification metadata (as recorded, not recomputed).
    for key, rel in [("saved_checks", "SAVED_XLSX_CHECKS.json"), ("portable", "PORTABLE_VERIFICATION.json")]:
        try:
            data[key] = json.loads(pkg.read(rel))
        except (KeyError, FileNotFoundError):  # not every package version ships these
            data[key] = None

    data["client_display"] = CLIENT_DISPLAY
    data["meta"] = {
        "package": pkg.name,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "evidence_rows": len(data["evidence"]),
        "rule_version": "development-2",
        "core_assessment": "2026-11-03",
        "crr_assessment": "2026-11-04",
        "export_date": "2026-11-05",
    }
    return data


def check(data: dict) -> None:
    """Fail loudly if the extracted payload disagrees with the package's own counts."""
    expected = {r["Signal"]: int(r["Evidence records"]) for r in data["overview"]["signals"]}
    got: dict = {}
    for e in data["evidence"]:
        got[e["signal_id"]] = got.get(e["signal_id"], 0) + 1
    for sig, n in expected.items():
        if got.get(sig, 0) != n:
            raise SystemExit(f"{sig}: overview says {n} evidence rows, extracted {got.get(sig, 0)}")
    missing = [e["evidence_id"] for e in data["evidence"] if e["evidence_id"] not in data["detail"]]
    if missing:
        raise SystemExit(f"{len(missing)} evidence rows have no Evidence detail record")


def logo_data_uri(pkg: Package) -> str:
    html = pkg.read("sample board/dashboard.html").decode("utf-8")  # the LAF sample board
    m = re.search(r'class="logo-mark"\s+src="(data:image/png;base64,[A-Za-z0-9+/=]+)"', html)
    if not m:
        raise SystemExit("HSBC logo not found in sample board/dashboard.html")
    return m.group(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="signal_workbooks_20261105_004",
                    help="signal workbook package: a folder or a .zip")
    ap.add_argument("--logo-from", default="signal_workbooks_20261105_003.zip",
                    help="package containing 'sample board/dashboard.html' (the LAF board)")
    ap.add_argument("--out", default=str(HERE / "dcm_signals_dashboard.html"))
    ap.add_argument("--json", help="optionally also write the extracted payload as JSON")
    args = ap.parse_args()

    pkg = Package(Path(args.src))
    data = extract(pkg)
    check(data)

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    payload = payload.replace("</", "<\\/")  # never terminate the <script> early
    template = (HERE / "template.html").read_text(encoding="utf-8")
    html = template.replace("__LOGO_DATA_URI__", logo_data_uri(Package(Path(args.logo_from)))).replace("__DASHBOARD_DATA__", payload)
    Path(args.out).write_text(html, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"Wrote {args.out}: {data['meta']['evidence_rows']} evidence rows, "
          f"{len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
