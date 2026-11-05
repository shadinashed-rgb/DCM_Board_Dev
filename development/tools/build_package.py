#!/usr/bin/env python3
"""Build the development-2 signal package (reports + workbooks) from a run folder.

Writes to the target folder:
  README.md, SIGNAL_DEFINITIONS.md, FINDINGS_AND_LIMITATIONS.md
  SIGNAL_OVERVIEW.xlsx and one workbook per signal/context
  (SIG01, SIG02, SIG03, SIG04, SIG06, SIG07, CTX_UTIL, CTX_CREDIT)

Workbook sheets: Summary (COUNTIFS formulas over Signal data), Signal data (compact
view, typed measures), Definitions, Findings, Sources, Owner review / Coverage where
applicable, Lineage (one row per evidence-to-source link) and Evidence detail (every
original field as saved text). Raw source sheets are unchanged and remain in the
archived signal_workbooks_20261105_003 package.

Usage (from development/):
  python3 tools/build_package.py runs/aligned_20261105_004 ../signal_workbooks_20261105_004 \
      --previous-package ../signal_workbooks_20261105_003.zip
Then recalculate formulas (the xlsx skill's recalc.py, or open and save in Excel).
"""
import argparse
from collections import Counter
import csv
import io
from pathlib import Path
import sys
import zipfile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signal_catalogue as C  # noqa: E402

FONT = 'Arial'
RED = 'DB0011'
HEAD_FILL = PatternFill('solid', fgColor='111111')
NUMERIC = {'current_drawn', 'previous_drawn', 'utilisation_amount', 'approved_limit', 'proposed_limit', 'event_age_days', 'event_lookback_days',
           'comparison_gap_days', 'drawing_in_threshold_currency', 'inferred_total_drawing', 'hsbc_participation_share_percent', 'covenant_headroom_turns'}
BOOLEAN = {'above_70_for_testing', 'recent_approval_for_testing', 'material_drawing_for_testing', 'covenant_pressure_for_testing', 'current_drawn_imputed_zero',
           'previous_drawn_imputed_zero', 'cat_a_eligible', 'stale', 'multiple_crrs_for_cin', 'approval_matches_creation_date'}
COLUMNS = {
    'SIG01': ['client', 'mastergroup_id', 'component', 'product_codes', 'clo_sub_limit_ids', 'drawn_field', 'currency', 'current_drawn', 'previous_drawn', 'metric_value',
              'previous_observation_date', 'comparison_gap_days', 'current_drawn_imputed_zero', 'previous_drawn_imputed_zero', 'limit_category', 'limit_category_basis',
              'cat_a_eligible', 'materiality_threshold', 'materiality_status', 'drawing_in_threshold_currency', 'hsbc_participation_share_percent', 'inferred_total_drawing',
              'material_drawing_for_testing', 'source', 'assessment_status', 'business_trigger', 'observation_date', 'assessment_date', 'stale', 'validation_reason', 'evidence_id'],
    'SIG02': ['client', 'mastergroup_id', 'facility_ids', 'product_codes', 'credit_proposal_serial_no', 'credit_approval_date', 'source_creation_dates',
              'approval_matches_creation_date', 'event_date', 'event_basis', 'event_age_days', 'event_lookback_days', 'recent_approval_for_testing', 'proposed_limit',
              'currency', 'conflicting_fields', 'credit_approval_source', 'source', 'component', 'assessment_status', 'business_trigger', 'observation_date',
              'assessment_date', 'stale', 'validation_reason', 'evidence_id'],
    'CTX_UTIL': ['client', 'mastergroup_id', 'drr_uids', 'facility_ids', 'product_codes', 'utilisation_amount', 'approved_limit', 'currency', 'metric_value',
                 'above_70_for_testing', 'conflicting_fields', 'source', 'component', 'assessment_status', 'business_trigger', 'observation_date', 'assessment_date',
                 'stale', 'validation_reason', 'evidence_id'],
    'CTX_CREDIT': ['client', 'mastergroup_id', 'source', 'component', 'cins', 'crr', 'crr_scale', 'rating_values', 'limit_categories', 'facility_ids', 'product_codes',
                   'advised_ind_values', 'crr_raw', 'previous_crr', 'proposed_crr', 'approved_crr', 'latest_record', 'multiple_crrs_for_cin', 'credit_proposal_serial_no',
                   'approval_date', 'assessment_status', 'business_trigger', 'observation_date', 'assessment_date', 'stale', 'validation_reason', 'evidence_id'],
}
EMPTY_COLUMNS = ['client', 'mastergroup_id', 'signal_id', 'source', 'component', 'assessment_status', 'business_trigger', 'observation_date', 'assessment_date', 'validation_reason', 'evidence_id']
COLUMNS['SIG06'] = ['client', 'mastergroup_id', 'signal_id', 'facility_ids', 'metric_value', 'approved_limit', 'covenant_headroom_turns', 'covenant_pressure_for_testing',
                    'source', 'component', 'assessment_status', 'business_trigger', 'observation_date', 'event_date', 'assessment_date', 'validation_reason', 'evidence_id']
FLAG = {'SIG01': ('material_drawing_for_testing', 'Material drawing test'), 'SIG02': ('recent_approval_for_testing', 'Approved <= 90 days'),
        'CTX_UTIL': ('above_70_for_testing', 'Utilisation > 70%'), 'SIG06': ('covenant_pressure_for_testing', 'Covenant pressure test')}
OWNER = {'SIG01': 'OWNER_REVIEW_SIG01.csv', 'SIG02': 'OWNER_REVIEW_SIG02.csv', 'CTX_UTIL': 'OWNER_REVIEW_CTX_UTIL.csv', 'CTX_CREDIT': 'OWNER_REVIEW_CTX_CREDIT.csv'}
COVERAGE_SOURCE = {'SIG03A': 'derivatives trades', 'SIG03B': 'pre-hedge enquiries', 'SIG04': 'kyc', 'SIG06': 'financial covenants', 'SIG07': 'CME call reports'}


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def typed(col, value, sig):
    if value in ('', None):
        return None
    if col in BOOLEAN:
        return value == 'True' if value in ('True', 'False') else value
    if col in NUMERIC or (col == 'metric_value' and sig in ('SIG01', 'CTX_UTIL')):
        try:
            number = float(value)
            return int(number) if number.is_integer() and abs(number) < 1e15 else number
        except ValueError:
            return value
    return value


def style_header(ws, row, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, color='FFFFFF', size=10)
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(vertical='bottom', wrap_text=True)


def titles(ws, lines):
    for i, line in enumerate(lines, 2):
        cell = ws.cell(row=i, column=1, value=line)
        cell.font = Font(name=FONT, bold=(i == 2), size=14 if i == 2 else 10, color=RED if i == 2 else '333333')
    return len(lines) + 3  # blank row, then header


def table(ws, start, header, rows, widths=None, text_cols=(), wrap_cols=()):
    for c, h in enumerate(header, 1):
        ws.cell(row=start, column=c, value=h)
    style_header(ws, start, len(header))
    for r, values in enumerate(rows, start + 1):
        for c, v in enumerate(values, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = Font(name=FONT, size=10)
            if header[c - 1] in text_cols or (isinstance(v, str) and v[:1].isdigit()):
                cell.number_format = '@'
            elif isinstance(v, float):
                cell.number_format = '#,##0.00'
            elif isinstance(v, int) and not isinstance(v, bool):
                cell.number_format = '#,##0'
            if header[c - 1] in wrap_cols:
                cell.alignment = Alignment(wrap_text=True, vertical='top')
    for c, h in enumerate(header, 1):
        ws.column_dimensions[get_column_letter(c)].width = (widths or {}).get(h, min(max(12, len(str(h)) + 2), 34))
    ws.freeze_panes = ws.cell(row=start + 1, column=1)
    return start + len(rows)


def lineage_rows(rows):
    out = []
    for r in rows:
        for field, role in (('source_record_references', 'current_evidence'), ('previous_source_record_references', 'prior_comparison')):
            for ref in [x.strip() for x in (r.get(field) or '').split('|') if x.strip()]:
                file, _, record = ref.rpartition(':record ')
                out.append([r['evidence_id'], r['client'], r['mastergroup_id'], r['source'], file, record, role, r['observation_date']])
    return out


def write_workbook(path, key, signals, rows, run):
    wb = Workbook()
    names = ' / '.join(f'{s} — {n}' for s, n, *_ in C.CATALOGUE if s in signals)
    cols = COLUMNS.get(key, EMPTY_COLUMNS)

    # Signal data first (Summary formulas reference it); sheets reordered at the end.
    data = wb.active
    data.title = 'Signal data'
    start = titles(data, [f'{key} signal data', f'Compact view; rule version {C.RULE_VERSION}. IDs, CRR codes and placeholders are text. Evidence detail keeps every original field.'])
    # The CSV keeps the development-1 column name; in development-2 it means "approved within 90 days".
    source_col = lambda c: 'recent_creation_for_testing' if c == 'recent_approval_for_testing' else c
    table(data, start, cols, [[typed(c, r.get(source_col(c), ''), key) for c in cols] for r in rows],
          text_cols={'mastergroup_id', 'clo_sub_limit_ids', 'facility_ids', 'drr_uids', 'cins', 'crr', 'crr_raw', 'crr_scale', 'credit_proposal_serial_no', 'evidence_id', 'previous_crr', 'proposed_crr', 'approved_crr'},
          widths={'evidence_id': 66, 'validation_reason': 60, 'clo_sub_limit_ids': 26, 'facility_ids': 26})
    first, last = start + 1, start + max(len(rows), 1)
    col = lambda name: get_column_letter(cols.index(name) + 1)

    # Summary
    ws = wb.create_sheet('Summary', 0)
    status_note = {s: st for s, _, _, st, _ in C.CATALOGUE}
    t = titles(ws, [f'{key} — {names}', 'Development evidence. Business triggers remain unverified.',
                    f"Core assessment: 3 Nov 2026. CRR assessment: 4 Nov 2026. Rules: {C.RULE_VERSION} (DCM meeting decisions).",
                    f"Evidence records: {len(rows)} · Coverage: {', '.join(sorted({status_note[s] for s in signals}))}"])
    flag = FLAG.get(key)
    header = ['Client', 'Mastergroup', 'Evidence records', 'Needs validation', 'Unavailable'] + ([flag[1]] if flag else [])
    for c, h in enumerate(header, 1):
        ws.cell(row=t, column=c, value=h)
    style_header(ws, t, len(header))
    for i, (client, mg) in enumerate(C.CLIENTS, t + 1):
        ws.cell(row=i, column=1, value=client)
        ws.cell(row=i, column=2, value=mg).number_format = '@'
        rng = lambda name: f"'Signal data'!${col(name)}${first}:${col(name)}${last}"
        ws.cell(row=i, column=3, value=f'=COUNTIFS({rng("mastergroup_id")},B{i})')
        ws.cell(row=i, column=4, value=f'=COUNTIFS({rng("mastergroup_id")},B{i},{rng("assessment_status")},"needs_validation")')
        ws.cell(row=i, column=5, value=f'=COUNTIFS({rng("mastergroup_id")},B{i},{rng("assessment_status")},"unavailable")')
        if flag:
            ws.cell(row=i, column=6, value=f'=COUNTIFS({rng("mastergroup_id")},B{i},{rng(flag[0])},TRUE)')
        for c in range(1, len(header) + 1):
            ws.cell(row=i, column=c).font = Font(name=FONT, size=10)
    total = t + len(C.CLIENTS) + 1
    ws.cell(row=total, column=1, value='Total').font = Font(name=FONT, bold=True, size=10)
    for c in range(3, len(header) + 1):
        L = get_column_letter(c)
        ws.cell(row=total, column=c, value=f'=SUM({L}{t + 1}:{L}{t + len(C.CLIENTS)})').font = Font(name=FONT, bold=True, size=10)
    note_row = total + 2
    for s in signals:
        for topic, finding, _ in C.FINDINGS.get(s, [])[:2]:
            ws.cell(row=note_row, column=1, value=f'{s} · {topic}: {finding}').font = Font(name=FONT, size=10)
            note_row += 1
    ws.cell(row=note_row, column=1, value='Counts are COUNTIFS formulas over the Signal data sheet. Lineage connects each record to source CSV records.').font = Font(name=FONT, size=10, italic=True)
    for L, w in zip('ABCDEF', (20, 14, 16, 16, 14, 22)):
        ws.column_dimensions[L].width = w

    # Definitions / Findings / Sources
    ws = wb.create_sheet('Definitions')
    t = titles(ws, [f'{key} definitions', 'Meeting decisions and user decisions supersede older discovery notes.'])
    table(ws, t, ['Signal', 'Topic', 'Current definition', 'Status'], [[s, *d] for s in signals for d in C.DEFINITIONS.get(s, [])],
          widths={'Signal': 10, 'Topic': 24, 'Current definition': 110, 'Status': 26}, wrap_cols={'Current definition'})
    ws = wb.create_sheet('Findings')
    t = titles(ws, [f'{key} findings', 'Signal-specific findings followed by shared limitations.'])
    table(ws, t, ['Signal', 'Topic', 'Finding', 'Required action'], [[s, *f] for s in signals for f in C.FINDINGS.get(s, [])] + [['All', *f] for f in C.COMMON_FINDINGS],
          widths={'Signal': 10, 'Topic': 24, 'Finding': 90, 'Required action': 60}, wrap_cols={'Finding', 'Required action'})
    ws = wb.create_sheet('Sources')
    t = titles(ws, [f'{key} sources', 'Workspace-relative source files (development/); raw sheets are in the archived 003 workbooks.'])
    table(ws, t, ['Signal', 'Workspace source file', 'Source table', 'Raw rows', 'Role'], [[s, *src] for s in signals for src in C.SOURCES.get(s, [])],
          widths={'Workspace source file': 58, 'Source table': 56, 'Role': 44})

    # Owner review or coverage
    if key in OWNER and (run / OWNER[key]).exists():
        orows = read(run / OWNER[key])
        ws = wb.create_sheet('Owner review')
        t = titles(ws, [f'{key} owner review', 'Questions that a source or business owner must answer before triggers are enabled.'])
        hdr = list(orows[0]) if orows else ['note']
        table(ws, t, hdr, [[typed(h, r[h], key) for h in hdr] for r in orows] or [['No records']],
              text_cols={'mastergroup_id', 'clo_sub_limit_ids', 'facility_ids', 'drr_uids', 'cins', 'credit_proposal_serial_no', 'evidence_id', 'crr', 'crr_raw'},
              widths={'owner_question': 90, 'evidence_id': 66}, wrap_cols={'owner_question'})
    no_source = [s for s in signals if s in COVERAGE_SOURCE]
    if no_source:
        ws = wb.create_sheet('Coverage')
        t = titles(ws, [f'{key} coverage', 'Missing, empty or unintegrated sources are not negative client activity.'])
        reason = {s: f for s in no_source for (_, f, _) in C.FINDINGS.get(s, [])[:1]}
        table(ws, t, ['Client', 'Mastergroup', 'Signal', 'Source', 'Coverage state', 'Reason'],
              [[client, mg, s, COVERAGE_SOURCE[s], next(st for x, _, _, st, _ in C.CATALOGUE if x == s), reason[s]] for s in no_source for client, mg in C.CLIENTS],
              widths={'Reason': 100}, wrap_cols={'Reason'})

    ws = wb.create_sheet('Lineage')
    t = titles(ws, [f'{key} lineage', 'One row per evidence-to-source record link, including the prior side of SIG01 comparisons.'])
    table(ws, t, ['Evidence ID', 'Client', 'Mastergroup', 'Source', 'CSV file', 'CSV record', 'Role', 'Evidence observation date'], lineage_rows(rows) or [['', '', '', '', '', '', '', '']],
          text_cols={'Evidence ID', 'Mastergroup', 'CSV record'}, widths={'Evidence ID': 66, 'CSV file': 40})
    ws = wb.create_sheet('Evidence detail')
    t = titles(ws, [f'{key} evidence detail', 'Every original evidence field as saved text; numeric/text conversion only happens in Signal data.'])
    hdr = list(rows[0]) if rows else EMPTY_COLUMNS
    table(ws, t, hdr, [[r.get(h) or None for h in hdr] for r in rows], text_cols=set(hdr))
    wb.move_sheet('Signal data', offset=-(len(wb.sheetnames) - 2))
    wb.save(path)


def write_overview(path, rows, previous_zip):
    wb = Workbook()
    idx = wb.active
    idx.title = 'Evidence index'
    t0 = titles(idx, ['Evidence index', 'One row per record; Summary and Client summary count this sheet with COUNTIFS.'])
    flag_of = lambda r: any(r.get(f) == 'True' for f in ('material_drawing_for_testing', 'recent_creation_for_testing', 'covenant_pressure_for_testing', 'above_70_for_testing'))
    table(idx, t0, ['signal_id', 'client', 'mastergroup_id', 'source', 'component', 'assessment_status', 'test_flag', 'evidence_id'],
          [[r['signal_id'], r['client'], r['mastergroup_id'], r['source'], r['component'], r['assessment_status'], flag_of(r), r['evidence_id']] for r in rows],
          text_cols={'mastergroup_id', 'evidence_id'}, widths={'evidence_id': 66})
    a, b = t0 + 1, t0 + len(rows)
    rng = lambda L: f"'Evidence index'!${L}${a}:${L}${b}"

    ws = wb.create_sheet('Summary', 0)
    t = titles(ws, ['Bond Radar — signal overview (development-2)', f'{len(rows)} development evidence and context records. Business triggers remain unverified.',
                    'Rules follow the DCM meeting decisions (docs/MEETING_ALIGNMENT_REVIEW.md).'])
    header = ['Signal', 'Name', 'Kind', 'Evidence records', 'Needs validation', 'Unavailable evidence', 'Test flags', 'Coverage', 'Workbook']
    for c, h in enumerate(header, 1):
        ws.cell(row=t, column=c, value=h)
    style_header(ws, t, len(header))
    for i, (sig, name, kind, cov, book) in enumerate(C.CATALOGUE, t + 1):
        vals = [sig, name, kind, f'=COUNTIFS({rng("A")},A{i})', f'=COUNTIFS({rng("A")},A{i},{rng("F")},"needs_validation")',
                f'=COUNTIFS({rng("A")},A{i},{rng("F")},"unavailable")', f'=COUNTIFS({rng("A")},A{i},{rng("G")},TRUE)', cov, f'{book}.xlsx' if book else '—']
        for c, v in enumerate(vals, 1):
            ws.cell(row=i, column=c, value=v).font = Font(name=FONT, size=10)
    tot = t + len(C.CATALOGUE) + 1
    ws.cell(row=tot, column=1, value='Total').font = Font(name=FONT, bold=True, size=10)
    for L in 'DEFG':
        ws[f'{L}{tot}'] = f'=SUM({L}{t + 1}:{L}{tot - 1})'
        ws[f'{L}{tot}'].font = Font(name=FONT, bold=True, size=10)
    notes = ['Test flags: SIG01 material drawing, SIG02 approved within 90 days, SIG06 covenant pressure, CTX_UTIL utilisation above 70% (context).',
             'SIG03A/SIG03B, SIG06 and SIG07 have no source; SIG04 has an empty export. None of these proves no activity.',
             'Investor-sales count dropped (DCM). SIG05 excluded (CME MNPI/entitlements).']
    for j, n in enumerate(notes, tot + 2):
        ws.cell(row=j, column=1, value=n).font = Font(name=FONT, size=10)
    for L, w in zip('ABCDEFGHI', (12, 46, 10, 16, 16, 18, 12, 28, 16)):
        ws.column_dimensions[L].width = w

    ws = wb.create_sheet('Client summary', 1)
    t = titles(ws, ['Signal evidence by client', 'Counts and development-test flags. Do not interpret as confirmed alerts.'])
    header = ['signal_id', 'signal_name', 'kind', 'client', 'mastergroup_id', 'evidence_rows', 'needs_validation_rows', 'unavailable_evidence_rows', 'test_flag_rows', 'coverage_status']
    for c, h in enumerate(header, 1):
        ws.cell(row=t, column=c, value=h)
    style_header(ws, t, len(header))
    i = t
    for sig, name, kind, cov, _ in C.CATALOGUE:
        for client, mg in C.CLIENTS:
            i += 1
            vals = [sig, name, kind, client, mg, f'=COUNTIFS({rng("A")},A{i},{rng("C")},E{i})', f'=COUNTIFS({rng("A")},A{i},{rng("C")},E{i},{rng("F")},"needs_validation")',
                    f'=COUNTIFS({rng("A")},A{i},{rng("C")},E{i},{rng("F")},"unavailable")', f'=COUNTIFS({rng("A")},A{i},{rng("C")},E{i},{rng("G")},TRUE)', cov]
            for c, v in enumerate(vals, 1):
                cell = ws.cell(row=i, column=c, value=v)
                cell.font = Font(name=FONT, size=10)
                if c == 5:
                    cell.number_format = '@'
    for L, w in zip('ABCDEFGHIJ', (11, 44, 10, 16, 14, 13, 20, 24, 14, 28)):
        ws.column_dimensions[L].width = w

    ws = wb.create_sheet('Definitions', 2)
    t = titles(ws, ['All signal definitions', 'Meeting decisions, user decisions, development rules and open definitions.'])
    table(ws, t, ['Signal', 'Topic', 'Current definition', 'Status'], [[s, *d] for s, *_ in C.CATALOGUE for d in C.DEFINITIONS.get(s, [])],
          widths={'Current definition': 110, 'Topic': 24, 'Status': 26}, wrap_cols={'Current definition'})
    ws = wb.create_sheet('Findings', 3)
    t = titles(ws, ['All current findings', 'Signal-specific findings and shared limitations.'])
    table(ws, t, ['Signal', 'Topic', 'Finding', 'Required action'], [[s, *f] for s, *_ in C.CATALOGUE for f in C.FINDINGS.get(s, [])] + [['All', *f] for f in C.COMMON_FINDINGS],
          widths={'Finding': 90, 'Required action': 60, 'Topic': 24}, wrap_cols={'Finding', 'Required action'})
    if previous_zip:
        z = zipfile.ZipFile(previous_zip)
        name = next(n for n in z.namelist() if n.endswith('/SIGNAL_OVERVIEW.xlsx') and not n.startswith('__MACOSX'))
        old = load_workbook(io.BytesIO(z.read(name)), data_only=True)
        for sheet in ('Source inventory', 'Counterparty raw'):
            src, dst = old[sheet], wb.create_sheet(sheet)
            for row in src.iter_rows(values_only=True):
                dst.append(list(row))
            for c in dst[6]:
                c.font = Font(name=FONT, bold=True, color='FFFFFF', size=10)
                c.fill = HEAD_FILL
            dst['A2'].font = Font(name=FONT, bold=True, size=14, color=RED)
            dst['A4'] = 'Carried forward unchanged from signal_workbooks_20261105_003.'
    wb.save(path)


def write_markdown(target, rows, run):
    by = Counter(r['signal_id'] for r in rows)
    lines = ['# Signal definitions — development-2 (meeting-aligned)', '',
             'Authority: the DCM meeting decisions (see `docs/MEETING_ALIGNMENT_REVIEW.md`) and explicit user decisions supersede older discovery notes. '
             'No business trigger is confirmed: every `definitions_verified` flag is false. Core assessment is 3 November 2026; CRR context assessment is 4 November.', '']
    for sig, name, kind, cov, _ in C.CATALOGUE:
        lines += [f'## {sig} — {name}', '', f'*Kind:* {kind} · *Coverage:* {cov} · *Records:* {by.get(sig, 0)}', '']
        lines += [f'- **{topic} ({status}):** {text}' for topic, text, status in C.DEFINITIONS.get(sig, [])] or ['- Excluded pending CME MNPI handling and entitlements; also the source for SIG07.']
        lines.append('')
    lines += ['## Dropped', '', '- **Number of investor sales:** dropped by DCM as a weak signal, because HSBC initiates the investor interaction. Jerome agreed.', '']
    (target / 'SIGNAL_DEFINITIONS.md').write_text('\n'.join(lines))

    lines = ['# Findings and limitations — 5 November 2026 (development-2)', '',
             f'The {len(rows)} records are development evidence and context. The additional DE extraction is deferred. '
             'Run: `development/runs/aligned_20261105_004` (review in its `REVIEW.md`).', '', '## All signals', '']
    lines += [f'- **{t}:** {f} {a}' for t, f, a in C.COMMON_FINDINGS] + ['']
    for sig, name, *_ in C.CATALOGUE:
        if sig in C.FINDINGS:
            lines += [f'## {sig} — {name}', ''] + [f'- **{t}:** {f} {a}' for t, f, a in C.FINDINGS[sig]] + ['']
    (target / 'FINDINGS_AND_LIMITATIONS.md').write_text('\n'.join(lines))

    readme = f"""# Bond Radar signal workbooks — development-2 (meeting-aligned)

Open **SIGNAL_OVERVIEW.xlsx** first. It summarises the catalogue: SIG01, SIG02, SIG03A, SIG03B, SIG04, SIG06 and SIG07, plus SIG05 (excluded) and the two context datasets `CTX_UTIL` and `CTX_CREDIT`. It also contains per-client counts, definitions, findings and the source inventory.

This package supersedes `signal_workbooks_20261105_003` for definitions and results. The 003 package is kept unchanged as the development-1 baseline: 626 records, with raw source sheets.

## What changed (DCM meeting decisions)

| Item | development-1 | development-2 |
|---|---|---|
| SIG01 | CLO REV drawn change, no threshold | Any **Cat A** bank facility (REV, TERM) drawing over **EUR 50m**; HSBC share and inferred total; separate USD-field comparison |
| SIG02 | `facility_creation_date`, 90-day test | **Credit approval date** (Application Ratings `approval_dt` via serial); 90-day test on approval |
| SIG03 | Single enquiry signal | **SIG03A** swap roll on maturing debt · **SIG03B** new pre-hedge enquiry |
| SIG06 | Utilisation > 70% | **Covenant breach or pressure** (leverage within 0.5x of maximum); utilisation → `CTX_UTIL` |
| SIG07 | Facilities/PVD category + CRR | **Call reports** (CME, not integrated); category + CRR → `CTX_CREDIT` |
| Investor sales | — | Dropped |

## Records

| Dataset | Records |
|---|---:|
""" + '\n'.join(f'| {s} — {n} | {by.get(s, 0)} |' for s, n, *_ in C.CATALOGUE) + f"""
| **Total** | **{len(rows)}** |

## Workbooks

Each workbook (SIG01, SIG02, SIG03, SIG04, SIG06, SIG07, CTX_UTIL and CTX_CREDIT) has these sheets:

1. **Summary** — counts by client; these are `COUNTIFS` formulas over Signal data.
2. **Signal data** — the compact view.
3. **Definitions**
4. **Findings**
5. **Sources**
6. **Owner review** or **Coverage**, where applicable.
7. **Lineage** — one row per source-record link.
8. **Evidence detail** — every original field as text.

Native identifiers, CRR codes and placeholders remain text. Amounts are in native currency; nothing is FX-converted or summed across sources.

## Rebuild

From `development/`:

```sh
python3 -B tools/extract_inputs.py
python3 -B run_reference.py --out runs/<new> --test-observed-links --ratings-input data/application_ratings_full
python3 -B tools/review_run.py runs/<new> --previous <development-1 combined CSV>
python3 -B tools/build_package.py runs/<new> ../<package folder> --previous-package ../signal_workbooks_20261105_003.zip
```

Then recalculate the workbook formulas, by opening and saving in Excel or by running LibreOffice headless.
"""
    (target / 'README.md').write_text(readme)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('run')
    p.add_argument('target')
    p.add_argument('--previous-package')
    a = p.parse_args()
    run, target = Path(a.run), Path(a.target)
    target.mkdir(parents=True, exist_ok=True)
    rows = read(run / 'BOND_RADAR_SIGNAL_EVIDENCE.csv')
    # Guard: catalogue findings quote counts that must match this run.
    by = Counter(r['signal_id'] for r in rows)
    assert by['SIG01'] == 8 and by['SIG02'] == 63 and by['CTX_UTIL'] == 442 and by['CTX_CREDIT'] == 118, by
    assert sum(r.get('recent_creation_for_testing') == 'True' for r in rows if r['signal_id'] == 'SIG02') == 9
    assert sum(r.get('above_70_for_testing') == 'True' for r in rows) == 5
    books = {}
    for sig, _, _, _, book in C.CATALOGUE:
        if book:
            books.setdefault(book, []).append(sig)
    for book, signals in books.items():
        write_workbook(target / f'{book}.xlsx', book, signals, [r for r in rows if r['signal_id'] in signals], run)
    write_overview(target / 'SIGNAL_OVERVIEW.xlsx', rows, a.previous_package)
    write_markdown(target, rows, run)
    print(f'Wrote {len(books) + 1} workbooks and 3 reports to {target}')


if __name__ == '__main__':
    main()
