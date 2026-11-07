#!/usr/bin/env python3
"""Build the Bond Radar signal-logic page: one flowchart per signal, plus the shared pipeline.

The flowcharts follow the development-2 rules as implemented in
development/pvd_client_cohort_lab/engine/bond_radar.py, alignment.py, sig07_crr.py and
portfolio.py. Charts are laid out on a grid and written as static inline SVG (no
scripts, no external files), so the page opens offline and prints one signal per page.

Usage (from the repository root):
  python3 docs/signal_flowcharts/build_signal_flowcharts.py
Writes docs/signal_flowcharts/Bond_Radar_Signal_Logic.html (standalone file) and, with
--fragment PATH, the same page without the document wrapper (for publishing).
"""
import argparse
from html import escape
from pathlib import Path
import textwrap

HERE = Path(__file__).resolve().parent

# ── Layout engine ─────────────────────────────────────────────────────────────
CHAR_W = {'main': 6.5, 'sub': 5.7, 'tag': 6.6}
LINE_H = {'main': 15, 'sub': 13.5, 'tag': 13}
ROW_GAP = 34
KIND_TAG = {'cand': 'TEST CANDIDATE', 'val': 'EVIDENCE · NEEDS VALIDATION', 'na': 'NOT ASSESSED', 'out': 'NOT PART OF THIS SIGNAL',
            'plan': 'PLANNED · NO SOURCE YET', 'ctx': 'CONTEXT · NOT A SIGNAL', 'trig': 'AFTER OWNER SIGN-OFF', 'flag': 'FLAGGED FOR REVIEW'}


def wrap(text, width, kind):
    chars = max(8, int(width / CHAR_W[kind]))
    lines = []
    for para in text.split('\n'):
        lines += textwrap.wrap(para, chars) or ['']
    return lines


class Chart:
    def __init__(self, cid, cols, widths, label):
        self.cid, self.cols, self.widths, self.label = cid, cols, widths, label
        self.nodes, self.edges = {}, []

    def node(self, nid, col, row, kind, text, sub=None, width=None, dashed=False, tag=None):
        self.nodes[nid] = dict(id=nid, col=col, row=row, kind=kind, text=text, sub=sub, w=width or self.widths[col], dashed=dashed, tag=tag)

    def edge(self, a, b, mode='down', label=None):
        self.edges.append((a, b, mode, label))

    def layout(self):
        for n in self.nodes.values():
            inner = n['w'] - (44 if n['kind'] == 'dec' else 24)
            n['main'] = wrap(n['text'], inner, 'main')
            n['subl'] = wrap(n['sub'], inner, 'sub') if n['sub'] else []
            n['tag'] = n['tag'] or KIND_TAG.get(n['kind'])
            h = 22 + len(n['main']) * LINE_H['main'] + len(n['subl']) * LINE_H['sub'] + (LINE_H['tag'] + 3 if n['tag'] else 0)
            n['h'] = max(h, 46)
        rows = sorted({n['row'] for n in self.nodes.values()})
        y, self.row_mid = 18, {}
        for r in rows:
            hmax = max(n['h'] for n in self.nodes.values() if n['row'] == r)
            self.row_mid[r] = y + hmax / 2
            y += hmax + ROW_GAP
        self.height = y - ROW_GAP + 18
        self.width = max(self.cols[n['col']] + n['w'] / 2 for n in self.nodes.values()) + 16
        for n in self.nodes.values():
            n['cx'], n['cy'] = self.cols[n['col']], self.row_mid[n['row']]
            n['x0'], n['x1'] = n['cx'] - n['w'] / 2, n['cx'] + n['w'] / 2
            n['y0'], n['y1'] = n['cy'] - n['h'] / 2, n['cy'] + n['h'] / 2

    def shape(self, n):
        cls = f"n n-{n['kind']}" + (' dashed' if n['dashed'] or n['kind'] in ('plan', 'trig') else '')
        x0, x1, y0, y1, cy = n['x0'], n['x1'], n['y0'], n['y1'], n['cy']
        if n['kind'] == 'dec':
            pts = f"{x0 + 16},{y0} {x1 - 16},{y0} {x1},{cy} {x1 - 16},{y1} {x0 + 16},{y1} {x0},{cy}"
            out = f'<polygon class="{cls}" points="{pts}"/>'
        else:
            rx = 18 if n['kind'] == 'start' else 7
            out = f'<rect class="{cls}" x="{x0:.1f}" y="{y0:.1f}" width="{n["w"]:.1f}" height="{n["h"]:.1f}" rx="{rx}"/>'
        lines = []
        if n['tag']:
            lines.append(('tag', n['tag']))
        lines += [('main', t) for t in n['main']] + [('sub', t) for t in n['subl']]
        total = sum(LINE_H[k] for k, _ in lines) + (3 if n['tag'] else 0)
        ty = cy - total / 2 + 10.5
        spans = []
        for i, (k, t) in enumerate(lines):
            spans.append(f'<tspan x="{n["cx"]:.1f}" y="{ty:.1f}" class="t-{k}">{escape(t)}</tspan>')
            ty += LINE_H[k] + (3 if k == 'tag' else 0)
        return out + f'<text class="nt nt-{n["kind"]}" text-anchor="middle">{"".join(spans)}</text>'

    def route(self, a, b, mode):
        f, t = self.nodes[a], self.nodes[b]
        if mode == 'down':
            sx, sy, ex, ey = f['cx'], f['y1'], t['cx'], t['y0']
            if abs(sx - ex) < 1:
                return f'M{sx:.1f},{sy:.1f} V{ey:.1f}', (sx + 7, sy + 15, 'start')
            mid = sy + min(18, (ey - sy) / 2)
            return f'M{sx:.1f},{sy:.1f} V{mid:.1f} H{ex:.1f} V{ey:.1f}', (sx + 7, sy + 13, 'start')
        if mode in ('right', 'left'):
            sgn = 1 if mode == 'right' else -1
            sx, sy = (f['x1'], f['cy']) if sgn > 0 else (f['x0'], f['cy'])
            lab = (sx + 7 * sgn, sy - 7, 'start' if sgn > 0 else 'end')
            if abs(t['cy'] - f['cy']) < 1:
                ex = t['x0'] if sgn > 0 else t['x1']
                return f'M{sx:.1f},{sy:.1f} H{ex:.1f}', lab
            ey = t['y0'] if t['cy'] > f['cy'] else t['y1']
            return f'M{sx:.1f},{sy:.1f} H{t["cx"]:.1f} V{ey:.1f}', lab
        if mode == 'join':
            # Merge into the vertical edge entering the target from above (no arrowhead of its own).
            sx, sy = f['cx'], f['y1']
            return f'M{sx:.1f},{sy:.1f} V{t["y0"] - 14:.1f} H{t["cx"]:.1f}', (sx + 7, sy + 15, 'start')
        if mode in ('dl', 'dr'):
            sx, sy = f['cx'], f['y1']
            ex = t['x1'] if mode == 'dl' else t['x0']
            return f'M{sx:.1f},{sy:.1f} V{t["cy"]:.1f} H{ex:.1f}', (sx + 7, sy + 15, 'start')
        raise ValueError(mode)

    def svg(self, caption):
        self.layout()
        mid = f'arw-{self.cid}'
        parts = [f'<svg class="flow" viewBox="0 0 {self.width:.0f} {self.height:.0f}" role="img" aria-label="{escape(self.label)}" '
                 f'style="min-width:{min(self.width, 640):.0f}px; --chart-w:{self.width * 1.08:.0f}px; margin:0 auto">',
                 f'<defs><marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                 f'<path class="arrowhead" d="M0,0 L10,5 L0,10 z"/></marker></defs>']
        labels = []
        for a, b, mode, label in self.edges:
            d, (lx, ly, anchor) = self.route(a, b, mode)
            marker = '' if mode == 'join' else f' marker-end="url(#{mid})"'
            parts.append(f'<path class="edge" d="{d}"{marker}/>')
            if label:
                cls = 'el el-yes' if label.lower().startswith('yes') else 'el el-no' if label.lower().startswith('no') else 'el'
                labels.append(f'<text class="{cls}" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{escape(label)}</text>')
        parts += [self.shape(n) for n in self.nodes.values()] + labels + ['</svg>']
        return f'<figure class="chart"><div class="chart-scroll">{"".join(parts)}</div><figcaption>{caption}</figcaption></figure>'


# ── Charts ────────────────────────────────────────────────────────────────────
def pipeline():
    c = Chart('pipe', [100, 300, 500, 700, 900], [176] * 5, 'Shared pipeline from internal sources to a business trigger')
    c.node('src', 0, 0, 'start', 'Internal sources', 'CLO, Facilities, DRR, PVD, KYC, covenants, Application Ratings, Counterparty Core')
    c.node('ext', 1, 0, 'step', 'Extract every client', 'Needed columns only; latest snapshot per partition; split into parts')
    c.node('chk', 2, 0, 'step', 'Check the inputs', 'All parts present, same headers, required columns')
    c.node('grp', 3, 0, 'step', 'Attach each record to a client group', 'See "Client group" below')
    c.node('obs', 4, 0, 'step', 'One observation per record and snapshot', 'Conflicting rows: value withheld, never picked')
    c.node('rule', 2, 1, 'dec', 'Apply the signal rule', 'one flowchart per signal below')
    c.node('na', 1, 2, 'na', 'Missing, invalid or conflicting data', 'never read as "no activity"')
    c.node('val', 2, 2, 'val', 'Assessed: rule not met, or definition not yet confirmed')
    c.node('cand', 3, 2, 'cand', 'Rule fired on development data')
    c.node('trig', 3, 3, 'trig', 'Business trigger', 'only once the owner signs off the definition')
    for a, b in (('src', 'ext'), ('ext', 'chk'), ('chk', 'grp'), ('grp', 'obs')):
        c.edge(a, b, 'right')
    c.edge('obs', 'rule', 'down')
    c.edge('rule', 'na', 'down')
    c.edge('rule', 'val', 'down')
    c.edge('rule', 'cand', 'down')
    c.edge('cand', 'trig', 'down', 'owner sign-off')
    return c.svg('Every signal goes through the same steps. Each evidence record ends with one status. '
                 'A test candidate becomes a business trigger only after the owner of the definition signs it off; until then nothing is an alert.')


def identity():
    c = Chart('id', [210, 520], [300, 260], 'How a record is attached to a client group')
    c.node('r', 0, 0, 'start', 'A record from any source', 'carries a CIN, GID, relationship ID or its own group ID')
    c.node('d0', 0, 1, 'dec', 'Does the source carry a valid mastergroup ID?', 'CLO rct_mastergroup_id, DRR drr_mastergroup_id (not "NO MSG")')
    c.node('g0', 1, 1, 'ctx', 'Use the source\'s own group', 'kept even when other routes disagree; the conflict is flagged', tag='GROUP ASSIGNED')
    c.node('d1', 0, 2, 'dec', 'Does Counterparty Core map the CIN or GID to a group?', 'latest snapshot on or before the as-of date, active status')
    c.node('g1', 1, 2, 'ctx', 'Use the Counterparty Core group', 'labelled counterparty_core_latest', tag='GROUP ASSIGNED')
    c.node('d2', 0, 3, 'dec', 'Does CLO or DRR record this CIN under one group?', 'only when Counterparty Core has no mapping')
    c.node('g2', 1, 3, 'ctx', 'Use that group', 'labelled native_source_cin_mastergroup', tag='GROUP ASSIGNED')
    c.node('d3', 0, 4, 'dec', 'Covenant record: does its relationship ID lead to one group?', 'Facilities relationship_id -> CIN -> group')
    c.node('g3', 1, 4, 'ctx', 'Use that group', 'labelled facilities_relationship_to_cin', tag='GROUP ASSIGNED')
    c.node('d4', 0, 5, 'dec', 'Is there a reviewed link?', 'e.g. PVD relationship -> group, supplied by the team')
    c.node('g4', 1, 5, 'ctx', 'Use the reviewed link', 'labelled with the reviewer\'s basis', tag='GROUP ASSIGNED')
    c.node('no', 0, 6, 'na', 'No client group', 'the record stays in the evidence file but is not counted for any client', tag='NO GROUP')
    c.edge('r', 'd0')
    for i, (d, g) in enumerate((('d0', 'g0'), ('d1', 'g1'), ('d2', 'g2'), ('d3', 'g3'), ('d4', 'g4'))):
        c.edge(d, g, 'right', 'Yes')
        c.edge(d, ['d1', 'd2', 'd3', 'd4', 'no'][i], 'down', 'No')
    return c.svg('Routes are tried in order. A CIN that points to two groups is ambiguous and gets no group. '
                 'Every record shows which route linked it. All routes are development links until the mapping is reviewed.')


def sig01():
    c = Chart('s1', [210, 520, 800], [300, 250, 230], 'SIG01 material drawing on a Cat A bank facility')
    c.node('s', 0, 0, 'start', 'CLO sub-limit at the latest snapshot', 'every client; two snapshots kept for the comparison')
    c.node('p', 0, 1, 'dec', 'Is the product REV or TERM?')
    c.node('p_no', 1, 1, 'out', 'Other or blank product', 'not assessed for SIG01')
    c.node('cat', 0, 2, 'step', 'Look up Cat A', 'Facilities limit_cat where facility_id = CLO sub_lim_id')
    c.node('two', 0, 3, 'step', 'Compare two drawn fields separately', 'default field (blank counts as 0, flagged) and the USD field; never mixed')
    c.node('pr', 0, 4, 'dec', 'Is there a prior snapshot for the same sub-limit?')
    c.node('pr_no', 1, 4, 'na', 'No prior snapshot', 'a drawing cannot be measured')
    c.node('ok', 0, 5, 'dec', 'Valid amounts, same currency, no conflicting rows?')
    c.node('ok_no', 1, 5, 'na', 'Invalid or conflicting data')
    c.node('dr', 0, 6, 'step', 'Drawing = drawn now minus drawn at the prior snapshot')
    c.node('imp', 0, 7, 'dec', 'Built only from blank (zero-filled) amounts?')
    c.node('imp_y', 1, 7, 'val', 'Not assessable', 'a blank is not an observed zero')
    c.node('pos', 0, 8, 'dec', 'Is the drawing above zero?')
    c.node('pos_no', 1, 8, 'val', 'No drawing increase')
    c.node('fx', 0, 9, 'dec', 'In EUR, or is an FX rate configured?')
    c.node('fx_no', 1, 9, 'val', 'FX rate not configured', 'no fallback conversion')
    c.node('h', 0, 10, 'dec', 'HSBC drawing at least EUR 50m?', 'HSBC\'s share can never exceed the whole facility')
    c.node('ps', 1, 10, 'dec', 'Is HSBC\'s participation share known?', 'sole lender = 100%')
    c.node('ps_no', 2, 10, 'val', 'Participation unknown', 'materiality undetermined')
    c.node('inf', 1, 11, 'dec', 'Inferred total at least EUR 50m?', 'inferred total = drawing / share')
    c.node('inf_no', 2, 11, 'val', 'Below EUR 50m')
    c.node('mat', 0, 12, 'step', 'Material drawing')
    c.node('ca', 0, 13, 'dec', 'Is the facility Cat A?')
    c.node('ca_no', 1, 13, 'val', 'Material, but not Cat A or Cat A unknown')
    c.node('cand', 0, 14, 'cand', 'Material drawing on a Cat A bank facility')
    c.node('trig', 0, 15, 'trig', 'Business trigger once the drawn field, FX source and participation are agreed')
    c.edge('s', 'p'); c.edge('p', 'p_no', 'right', 'No'); c.edge('p', 'cat', 'down', 'Yes'); c.edge('cat', 'two'); c.edge('two', 'pr')
    c.edge('pr', 'pr_no', 'right', 'No'); c.edge('pr', 'ok', 'down', 'Yes')
    c.edge('ok', 'ok_no', 'right', 'No'); c.edge('ok', 'dr', 'down', 'Yes'); c.edge('dr', 'imp')
    c.edge('imp', 'imp_y', 'right', 'Yes'); c.edge('imp', 'pos', 'down', 'No')
    c.edge('pos', 'pos_no', 'right', 'No'); c.edge('pos', 'fx', 'down', 'Yes')
    c.edge('fx', 'fx_no', 'right', 'No'); c.edge('fx', 'h', 'down', 'Yes')
    c.edge('h', 'ps', 'right', 'No'); c.edge('h', 'mat', 'down', 'Yes')
    c.edge('ps', 'ps_no', 'right', 'No'); c.edge('ps', 'inf', 'down', 'Yes')
    c.edge('inf', 'inf_no', 'right', 'No'); c.edge('inf', 'mat', 'dl', 'Yes')
    c.edge('mat', 'ca'); c.edge('ca', 'ca_no', 'right', 'No'); c.edge('ca', 'cand', 'down', 'Yes'); c.edge('cand', 'trig')
    return c.svg('Both drawn fields run through the same steps. Materiality is tested on HSBC\'s drawing first, because HSBC\'s share '
                 'can never exceed the whole facility; only if that is below EUR 50m is the inferred total tested, and only when the participation share is known.')


def sig02():
    c = Chart('s2', [210, 520, 800], [300, 250, 220], 'SIG02 new RCF, term loan or bridge dated by credit approval')
    c.node('s', 0, 0, 'start', 'Facility at the latest snapshot', 'per source system and country; version effective on that date')
    c.node('cf', 0, 1, 'dec', 'Does the same facility key have conflicting products or dates?')
    c.node('cf_y', 1, 1, 'na', 'Withheld', 'not resolved by picking one row')
    c.node('ar', 0, 2, 'dec', 'Does the credit proposal serial link to an approval date?', 'Application Ratings approval_dt, same CIN preferred')
    c.node('alt', 1, 2, 'dec', 'Valid loan_approva_dt or facility_creation_date?')
    c.node('alt_no', 2, 2, 'na', 'No valid event date')
    c.node('ev1', 0, 3, 'step', 'Event date = credit approval date')
    c.node('ev2', 1, 3, 'step', 'Event date = that date', 'labelled "candidate approval date"')
    c.node('fut', 0, 4, 'dec', 'Is the event date after the snapshot?')
    c.node('fut_y', 1, 4, 'na', 'Event date in the future', 'an approval cannot post-date the snapshot')
    c.node('age', 0, 5, 'step', 'Age = assessment date minus event date')
    c.node('rec', 0, 6, 'dec', 'Approved in the last 90 days?')
    c.node('rec_no', 1, 6, 'val', 'Older facility', 'kept as context')
    c.node('cand', 0, 7, 'cand', 'New facility approved in the last 90 days')
    c.node('trig', 0, 8, 'trig', 'Business trigger once the product is confirmed as RCF, term loan or bridge')
    c.edge('s', 'cf'); c.edge('cf', 'cf_y', 'right', 'Yes'); c.edge('cf', 'ar', 'down', 'No')
    c.edge('ar', 'ev1', 'down', 'Yes'); c.edge('ar', 'alt', 'right', 'No')
    c.edge('alt', 'alt_no', 'right', 'No'); c.edge('alt', 'ev2', 'down', 'Yes')
    c.edge('ev1', 'fut'); c.edge('ev2', 'fut', 'join')
    c.edge('fut', 'fut_y', 'right', 'Yes'); c.edge('fut', 'age', 'down', 'No')
    c.edge('age', 'rec'); c.edge('rec', 'rec_no', 'right', 'No'); c.edge('rec', 'cand', 'down', 'Yes'); c.edge('cand', 'trig')
    return c.svg('The credit approval date is preferred because it comes before signing. Facilities\' own approval field is a placeholder today, '
                 'so the creation date is only a fallback and is labelled as such on the record.')


def sig03a():
    c = Chart('s3a', [210, 520], [300, 250], 'SIG03A swap roll on maturing debt (planned)')
    c.node('s', 0, 0, 'start', 'Derivatives trades per client', 'source not identified yet', dashed=True)
    c.node('sw', 0, 1, 'step', 'Swaps: FX swap first, then IRS and CCS')
    c.node('ln', 0, 2, 'dec', 'Is the swap tied to debt that is maturing?')
    c.node('ln_no', 1, 2, 'out', 'Not a SIG03A event')
    c.node('rl', 0, 3, 'dec', 'Rolled or novated within the lookback?')
    c.node('rl_no', 1, 3, 'val', 'Existing swap, no roll')
    c.node('cand', 0, 4, 'plan', 'Swap roll on maturing debt', 'would be a test candidate')
    c.edge('s', 'sw'); c.edge('sw', 'ln'); c.edge('ln', 'ln_no', 'right', 'No'); c.edge('ln', 'rl', 'down', 'Yes')
    c.edge('rl', 'rl_no', 'right', 'No'); c.edge('rl', 'cand', 'down', 'Yes')
    return c.svg('Planned logic for discussion. Needed fields: trade ID, product, trade and maturity dates, notional and currency, linked debt and a roll or novation flag.')


def sig03b():
    c = Chart('s3b', [210, 520], [300, 250], 'SIG03B new pre-hedge swap enquiry (planned)')
    c.node('s', 0, 0, 'start', 'Pre-hedge enquiries and pricing requests', 'not captured in markets systems today; Bloomberg chat is an open option', dashed=True)
    c.node('eq', 0, 1, 'step', 'Enquiry for a new swap: FX swap first')
    c.node('pp', 0, 2, 'dec', 'Linked to new financing or an issuance?')
    c.node('pp_no', 1, 2, 'out', 'Not a SIG03B event')
    c.node('lb', 0, 3, 'dec', 'Within the lookback?')
    c.node('lb_no', 1, 3, 'val', 'Older enquiry', 'kept as context')
    c.node('cand', 0, 4, 'plan', 'New pre-hedge enquiry', 'would be a test candidate')
    c.edge('s', 'eq'); c.edge('eq', 'pp'); c.edge('pp', 'pp_no', 'right', 'No'); c.edge('pp', 'lb', 'down', 'Yes')
    c.edge('lb', 'lb_no', 'right', 'No'); c.edge('lb', 'cand', 'down', 'Yes')
    return c.svg('Planned logic for discussion. SIG03A and SIG03B point the same way but are treated as independent signals, as agreed with DCM.')


def sig04():
    c = Chart('s4', [210, 520], [300, 250], 'SIG04 KYC onboarding or signatory refresh')
    c.node('s', 0, 0, 'start', 'KYC case', 'cases requested in the last 365 days; the target export is empty today')
    c.node('ok', 0, 1, 'dec', 'Valid case date, not after the snapshot, no conflicting rows?')
    c.node('ok_no', 1, 1, 'na', 'Invalid or conflicting case')
    c.node('pu', 0, 2, 'dec', 'Purpose is new-to-bank (NTB) or trigger (TRG)?', 'development codes; meanings to be agreed')
    c.node('pu_no', 1, 2, 'val', 'Routine review', 'e.g. periodic or remediation; kept, not flagged')
    c.node('lb', 0, 3, 'dec', 'Requested in the last 90 days?')
    c.node('lb_no', 1, 3, 'val', 'Older case', 'kept, not flagged')
    c.node('fl', 0, 4, 'flag', 'Recent onboarding or trigger case', 'needs validation; a trigger case alone is not a financing event')
    c.node('trig', 0, 5, 'trig', 'Business trigger once purposes and case dates are agreed')
    c.edge('s', 'ok'); c.edge('ok', 'ok_no', 'right', 'No'); c.edge('ok', 'pu', 'down', 'Yes')
    c.edge('pu', 'pu_no', 'right', 'No'); c.edge('pu', 'lb', 'down', 'Yes')
    c.edge('lb', 'lb_no', 'right', 'No'); c.edge('lb', 'fl', 'down', 'Yes'); c.edge('fl', 'trig')
    return c.svg('The rule is built, but there is no target data yet. Recent NTB or trigger cases are flagged for review rather than listed as candidates.')


def sig05():
    c = Chart('s5', [210, 520], [300, 250], 'SIG05 call-report keywords (excluded)')
    c.node('s', 0, 0, 'start', 'Call reports posted by GRBs in CME', dashed=True)
    c.node('gv', 0, 1, 'dec', 'MNPI handling and entitlements approved?')
    c.node('gv_no', 1, 1, 'out', 'Excluded today')
    c.node('kw', 0, 2, 'dec', 'Report mentions acquisition, drawing, opportunistic or liquidity?')
    c.node('kw_no', 1, 2, 'out', 'No keyword')
    c.node('cand', 0, 3, 'plan', 'Call-report keyword', 'would be a candidate for review')
    c.edge('s', 'gv'); c.edge('gv', 'gv_no', 'right', 'No'); c.edge('gv', 'kw', 'down', 'Yes')
    c.edge('kw', 'kw_no', 'right', 'No'); c.edge('kw', 'cand', 'down', 'Yes')
    return c.svg('Excluded until the MNPI and entitlement questions are resolved. SIG07 depends on the same source.')


def sig06():
    c = Chart('s6', [210, 520, 800], [300, 250, 220], 'SIG06 financial covenant breach or pressure')
    c.node('s', 0, 0, 'start', 'Covenant test', 'tests reported or due in the last 400 days; no financial covenant data today')
    c.node('fin', 0, 1, 'dec', 'Is it a financial covenant?')
    c.node('fin_no', 1, 1, 'na', 'Non-financial obligation', '"Overdue" reporting is not a breach')
    c.node('val', 0, 2, 'dec', 'Actual value, one threshold and a supported operator?')
    c.node('val_no', 1, 2, 'na', 'Incomplete test')
    c.node('dt', 0, 3, 'dec', 'Test date valid and in the last 90 days?')
    c.node('dt_no', 1, 3, 'na', 'Outside the window')
    c.node('mx', 0, 4, 'dec', 'Is it a maximum covenant?', 'e.g. net debt / EBITDA must stay at or below a level')
    c.node('cmp', 1, 4, 'dec', 'Does the compliance condition fail?', 'e.g. a minimum interest cover')
    c.node('cmp_y', 2, 4, 'flag', 'Breach recorded', 'the half-turn pressure rule applies to maximum covenants only')
    c.node('cmp_n', 1, 5, 'val', 'Compliant')
    c.node('hd', 0, 5, 'step', 'Headroom = maximum minus actual', 'in turns of leverage')
    c.node('br', 0, 6, 'dec', 'Does the compliance condition fail?', 'actual above the maximum')
    c.node('br_y', 1, 6, 'cand', 'Covenant breach', 'negative headroom')
    c.node('pr', 0, 7, 'dec', 'Headroom of half a turn or less?', 'e.g. 2.6x against a 3.0x maximum')
    c.node('pr_no', 1, 7, 'val', 'Comfortable headroom')
    c.node('cand', 0, 8, 'cand', 'Covenant pressure')
    c.node('trig', 0, 9, 'trig', 'Business trigger once test status, units and operators are confirmed')
    c.edge('s', 'fin'); c.edge('fin', 'fin_no', 'right', 'No'); c.edge('fin', 'val', 'down', 'Yes')
    c.edge('val', 'val_no', 'right', 'No'); c.edge('val', 'dt', 'down', 'Yes')
    c.edge('dt', 'dt_no', 'right', 'No'); c.edge('dt', 'mx', 'down', 'Yes')
    c.edge('mx', 'cmp', 'right', 'No'); c.edge('cmp', 'cmp_y', 'right', 'Yes'); c.edge('cmp', 'cmp_n', 'down', 'No')
    c.edge('mx', 'hd', 'down', 'Yes'); c.edge('hd', 'br')
    c.edge('br', 'br_y', 'right', 'Yes'); c.edge('br', 'pr', 'down', 'No')
    c.edge('pr', 'pr_no', 'right', 'No'); c.edge('pr', 'cand', 'down', 'Yes'); c.edge('cand', 'trig')
    return c.svg('Pressure follows the DCM definition: leverage within half a turn of the covenant maximum (2.5x against 3.0x, 3.5x against 4.0x, 1.5x against 2.0x). '
                 'Facility utilisation is not used here; it is shown separately as context.')


def sig07():
    c = Chart('s7', [210, 520], [300, 250], 'SIG07 rating advisory request (planned)')
    c.node('s', 0, 0, 'start', 'Senior banker discusses rating advisory with the client')
    c.node('cr', 0, 1, 'step', 'Conversation recorded in the call report (CME)')
    c.node('gv', 0, 2, 'dec', 'CME access approved (MNPI, entitlements)?')
    c.node('gv_no', 1, 2, 'out', 'Not integrated today')
    c.node('rq', 0, 3, 'dec', 'Does the report record a request for HSBC as rating advisor?')
    c.node('rq_no', 1, 3, 'out', 'No request')
    c.node('cand', 0, 4, 'plan', 'Rating advisory request', 'would be a test candidate')
    c.edge('s', 'cr'); c.edge('cr', 'gv'); c.edge('gv', 'gv_no', 'right', 'No'); c.edge('gv', 'rq', 'down', 'Yes')
    c.edge('rq', 'rq_no', 'right', 'No'); c.edge('rq', 'cand', 'down', 'Yes')
    return c.svg('Requests are rare and will not be automated in AI Markets; they are only recorded in call reports. Credit ratings (CRR) are shown as context, not as this signal.')


def ctx_util():
    c = Chart('cu', [210, 520], [300, 250], 'Utilisation context')
    c.node('s', 0, 0, 'start', 'Exposure at the latest snapshot', 'DRR, CLO and PVD, each at its own grain')
    c.node('v', 0, 1, 'dec', 'Valid drawn amount and a limit above zero?')
    c.node('v_no', 1, 1, 'na', 'Missing or invalid amounts')
    c.node('cc', 0, 2, 'dec', 'Same currency, units and scope for both amounts?')
    c.node('cc_no', 1, 2, 'na', 'Incompatible amounts', 'no FX fallback')
    c.node('cf', 0, 3, 'dec', 'No conflicting rows for the exposure?')
    c.node('cf_no', 1, 3, 'na', 'Withheld')
    c.node('u', 0, 4, 'step', 'Utilisation = drawn / limit x 100')
    c.node('h', 0, 5, 'dec', 'Above 70%?')
    c.node('h_y', 1, 5, 'ctx', 'High utilisation', 'shown as context')
    c.node('h_n', 0, 6, 'ctx', 'Utilisation shown')
    c.edge('s', 'v'); c.edge('v', 'v_no', 'right', 'No'); c.edge('v', 'cc', 'down', 'Yes')
    c.edge('cc', 'cc_no', 'right', 'No'); c.edge('cc', 'cf', 'down', 'Yes')
    c.edge('cf', 'cf_no', 'right', 'No'); c.edge('cf', 'u', 'down', 'Yes'); c.edge('u', 'h')
    c.edge('h', 'h_y', 'right', 'Yes'); c.edge('h', 'h_n', 'down', 'No')
    return c.svg('Context beside the signals. It is never covenant pressure, and nothing is summed across sources, currencies or parent and child limits.')


def ctx_credit():
    c = Chart('cc', [190, 490, 780], [280, 260, 220], 'Credit category and rating context')
    c.node('f', 0, 0, 'start', 'Facilities and PVD', 'limit category (CAT-A/B/S), advised flag, grades, PVD CRR and category')
    c.node('a', 1, 0, 'start', 'Application Ratings', 'CRR per credit application')
    c.node('fc', 0, 1, 'ctx', 'Credit category', 'Cat A also decides SIG01 eligibility')
    c.node('sel', 1, 1, 'step', 'Latest snapshot per source, country and CARM, then effective periods')
    c.node('pop', 1, 2, 'dec', 'Final CRR populated (not blank or N/A)?')
    c.node('pop_no', 2, 2, 'na', 'CRR unavailable', 'no fallback to other CRR states')
    c.node('lk', 1, 3, 'dec', 'Does the CIN lead to one client group?')
    c.node('lk_no', 2, 3, 'na', 'Group not resolved')
    c.node('crr', 1, 4, 'ctx', 'CRR shown', 'competing CRRs kept side by side; no averaging or "best" pick')
    c.edge('f', 'fc'); c.edge('a', 'sel'); c.edge('sel', 'pop')
    c.edge('pop', 'pop_no', 'right', 'No'); c.edge('pop', 'lk', 'down', 'Yes')
    c.edge('lk', 'lk_no', 'right', 'No'); c.edge('lk', 'crr', 'down', 'Yes')
    return c.svg('Context only. Rating advisory itself comes from call reports (SIG07). CRR codes are categorical; no numeric direction is assumed.')


# ── Content ───────────────────────────────────────────────────────────────────
SECTIONS = [
    dict(id='sig01', code='SIG01', name='Material drawing on a Cat A bank facility', kind='Signal', status=('Rule built · data gap', 'amber'),
         chart=sig01,
         means='A client draws more than EUR 50m on any Cat A bank facility: an RCF, a term loan or a bilateral facility. The facility does not have to be labelled RCF.',
         why='When a company needs cash it usually draws on its bank lines first. A large drawing can precede refinancing in the bond market.',
         rule='Drawing = drawn amount now minus drawn amount at the prior snapshot. Material if HSBC\'s drawing is at least EUR 50m, or if the inferred total (HSBC drawing / HSBC participation share) is. Only Cat A facilities count.',
         data='CLO sub-limits: drawn amount (two fields, compared separately), currency, sole-lender flag. Facilities: limit_cat for Cat A.',
         today='Built and tested. The default drawn field is blank in CLO, and no FX source or participation share has been supplied, so no drawing can be called material yet.',
         open='Authoritative drawn amount (LoanIQ), FX source and date, HSBC participation share, comparison period.'),
    dict(id='sig02', code='SIG02', name='New RCF, term loan or bridge', kind='Signal', status=('Working', 'green'), chart=sig02,
         means='A new RCF, term loan or bridge facility, dated by the internal credit approval date.',
         why='New bank facilities, bridges in particular, are often refinanced in the bond market. The approval date gives an earlier signal than signing.',
         rule='Event date = credit approval date from Application Ratings, linked through the credit proposal serial number. Candidate if approved in the last 90 days.',
         data='Facilities: facility, product, credit proposal serial, creation date, proposed limit. Application Ratings: approval date.',
         today='Working. In the three-client run, 9 facilities were approved within 90 days.',
         open='Credit team to confirm the approval relates to the new facility, not a later review. Product codes for RCF, term loan and bridge.'),
    dict(id='sig03a', code='SIG03A', name='Swap roll on maturing debt', kind='Signal', status=('No source', 'grey'), chart=sig03a,
         means='A client rolls an existing swap that is tied to debt that is maturing.',
         why='Rolling the hedge on maturing debt points to refinancing of that debt.',
         rule='Planned: swap linked to maturing debt and rolled or novated within the lookback. FX swaps first.',
         data='Needs derivatives trade data: trade ID, product, dates, notional, linked debt, roll flag.',
         today='No source identified, so no evidence.', open='Locate the derivatives trade source and its owner.'),
    dict(id='sig03b', code='SIG03B', name='New pre-hedge swap enquiry', kind='Signal', status=('No source', 'grey'), chart=sig03b,
         means='A client asks HSBC about a new pre-hedge swap ahead of an issuance.',
         why='Pre-hedging, FX swaps in particular, is a strong sign that an issuance is being prepared.',
         rule='Planned: an enquiry for a new swap, linked to new financing, within the lookback.',
         data='Needs enquiry or pricing-request records: client, date, product, status, notional, purpose.',
         today='The signal does not exist in markets systems today.', open='Decide on a source (Bloomberg chat was suggested) and the event definition.'),
    dict(id='sig04', code='SIG04', name='KYC onboarding or signatory refresh', kind='Signal', status=('Empty export', 'grey'), chart=sig04,
         means='A new entity is onboarded, or KYC is refreshed for signatories.',
         why='A new issuing entity or new signatories can precede a bond transaction.',
         rule='Recent cases (90 days) with purpose new-to-bank or trigger are flagged for review.',
         data='KYC: case ID, purpose code, request date, status.',
         today='The target KYC export is empty.', open='A known target case, and the meaning of each purpose code.'),
    dict(id='sig05', code='SIG05', name='Call-report keywords', kind='Excluded', status=('Excluded', 'grey'), chart=sig05,
         means='Keywords such as acquisition, drawing, opportunistic or liquidity in call reports posted by GRBs.',
         why='Banker notes can reveal financing plans early.',
         rule='Planned keyword search once access is approved.', data='CME call reports.',
         today='Excluded pending MNPI handling and entitlements.', open='Governance decision on CME access.'),
    dict(id='sig06', code='SIG06', name='Financial covenant breach or pressure', kind='Signal', status=('Rule built · no data', 'amber'), chart=sig06,
         means='A covenant breach, or leverage within half a turn of the covenant maximum.',
         why='Covenant pressure can lead to refinancing, or to a hybrid transaction.',
         rule='Headroom = maximum minus actual. Pressure when headroom is half a turn or less; breach when the condition fails.',
         data='Covenant tests: type, actual value, threshold, operator, test date, approval status.',
         today='Built and tested, but no genuine financial covenant data has been supplied.',
         open='Financial covenant source (net debt / EBITDA actual and maximum). The DRR covenant-waiver date is a lead to check.'),
    dict(id='sig07', code='SIG07', name='Rating advisory request', kind='Signal', status=('Waiting on CME', 'grey'), chart=sig07,
         means='A client asks about HSBC acting as rating advisor.',
         why='A direct sign of interest in the capital markets. Requests are rare but very relevant.',
         rule='Planned: a request recorded in a call report.', data='CME call reports, as for SIG05.',
         today='Not integrated.', open='CME access decision (MNPI, entitlements).'),
    dict(id='ctx-util', code='Context', name='Facility utilisation', kind='Context', status=('Context', 'ctx'), chart=ctx_util,
         means='How much of a facility is used: drawn amount divided by limit.',
         why='Supporting view of facility usage beside the signals.',
         rule='Only when both amounts share currency, units and scope. Above 70% is highlighted.',
         data='DRR, CLO and PVD limits and utilisation.',
         today='In the three-client run, 5 ratios were above 70%.', open='Product and participation scope. Utilisation is not covenant pressure.'),
    dict(id='ctx-credit', code='Context', name='Credit category and rating', kind='Context', status=('Context', 'ctx'), chart=ctx_credit,
         means='Each facility\'s credit category (Cat A, B or S) and the client\'s credit risk rating (CRR).',
         why='Cat A decides which drawings count for SIG01. The CRR gives credit context.',
         rule='Final CRR with its scale; blank or N/A stays unavailable. Competing CRRs are kept side by side.',
         data='Facilities limit_cat and grades, PVD CRR, Application Ratings CRR.',
         today='In the three-client run, 18 CRRs were populated.', open='CRR scale and version meanings; definitions of CAT-A, B and S.'),
]


def section(s):
    defs = [('What it means', s['means']), ('Why DCM cares', s['why']), ('Rule', s['rule']), ('Data used', s['data']),
            ('Status today', s['today']), ('Open points', s['open'])]
    items = ''.join(f'<div class="def"><dt>{t}</dt><dd>{escape(v)}</dd></div>' for t, v in defs)
    label, tone = s['status']
    return (f'<section class="sig" id="{s["id"]}"><header class="sig-head"><p class="eyebrow">{escape(s["code"]) if s["code"] == s["kind"] else escape(s["code"]) + " · " + escape(s["kind"])}</p>'
            f'<h2>{escape(s["name"])}</h2><span class="chip chip-{tone}">{escape(label)}</span></header>'
            f'<div class="sig-body"><dl class="defs">{items}</dl>{s["chart"]()}</div></section>')


LEGEND = [('n-start', 'Source or start'), ('n-step', 'Step'), ('n-dec', 'Decision'), ('n-cand', 'Test candidate'),
          ('n-flag', 'Flagged for review'), ('n-val', 'Evidence, needs validation'), ('n-na', 'Not assessed: data missing or conflicting'),
          ('n-out', 'Not part of the signal'), ('n-ctx', 'Context, not a signal'), ('n-plan dashed', 'Planned, no source yet'), ('n-trig dashed', 'After owner sign-off')]

CSS = """
:root{
  /* Layout: sticky signal index on the left, one section per signal; each section pairs a definition panel with its flowchart. */
  --bg:#f3f3f3; --surface:#ffffff; --soft:#f8f8f8; --fg:#1d1d1d; --muted:#5c5c5c; --line:#d7d7d7; --line-strong:#a9a9a9;
  --accent:#db0011; --edge:#6b6b6b;
  --start-bg:#1d1d1d; --start-fg:#ffffff; --dec-bg:#ffffff; --dec-line:#1d1d1d;
  --cand-bg:#fde7ea; --cand-line:#c4000f; --cand-fg:#8f0010;
  --flag-bg:#fff2db; --flag-line:#b07800; --val-bg:#fff7e8; --val-line:#d9b25c; --val-fg:#6b4a00;
  --na-bg:#efefef; --na-line:#b3b3b3; --na-fg:#555555; --out-bg:#ffffff; --out-line:#c9c9c9;
  --ctx-bg:#eef2f3; --ctx-line:#8fa3a8; --ctx-fg:#2f4a50; --trig-bg:#ffffff; --trig-line:#1d1d1d;
  --green:#1c5c35; --green-bg:#e7f5ec;
  --font:"Univers Next for HSBC","Helvetica Neue",Arial,sans-serif;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --bg:#121212; --surface:#1b1b1b; --soft:#202020; --fg:#ececec; --muted:#a9a9a9; --line:#333333; --line-strong:#5a5a5a;
  --accent:#ff4d5a; --edge:#a0a0a0; --start-bg:#ececec; --start-fg:#121212; --dec-bg:#1b1b1b; --dec-line:#ececec;
  --cand-bg:#3a1418; --cand-line:#ff5c69; --cand-fg:#ffb3ba; --flag-bg:#3a2c10; --flag-line:#e0a93a; --val-bg:#2b2416; --val-line:#9c7d3c; --val-fg:#f0d39a;
  --na-bg:#262626; --na-line:#555555; --na-fg:#bdbdbd; --out-bg:#1b1b1b; --out-line:#4a4a4a;
  --ctx-bg:#1b2628; --ctx-line:#58747a; --ctx-fg:#bfd7dc; --trig-bg:#1b1b1b; --trig-line:#ececec; --green:#8fd6a8; --green-bg:#16301f; color-scheme:dark; } }
:root[data-theme="dark"]{
  --bg:#121212; --surface:#1b1b1b; --soft:#202020; --fg:#ececec; --muted:#a9a9a9; --line:#333333; --line-strong:#5a5a5a;
  --accent:#ff4d5a; --edge:#a0a0a0; --start-bg:#ececec; --start-fg:#121212; --dec-bg:#1b1b1b; --dec-line:#ececec;
  --cand-bg:#3a1418; --cand-line:#ff5c69; --cand-fg:#ffb3ba; --flag-bg:#3a2c10; --flag-line:#e0a93a; --val-bg:#2b2416; --val-line:#9c7d3c; --val-fg:#f0d39a;
  --na-bg:#262626; --na-line:#555555; --na-fg:#bdbdbd; --out-bg:#1b1b1b; --out-line:#4a4a4a;
  --ctx-bg:#1b2628; --ctx-line:#58747a; --ctx-fg:#bfd7dc; --trig-bg:#1b1b1b; --trig-line:#ececec; --green:#8fd6a8; --green-bg:#16301f; color-scheme:dark; }
*{box-sizing:border-box}
body{background:var(--bg); color:var(--fg); font-family:var(--font); margin:0; line-height:1.5}
.wrap{max-width:1320px; margin:0 auto; padding-block:28px 64px; padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px));
  display:grid; grid-template-columns:220px minmax(0,1fr); gap:28px}
nav.index{position:sticky; top:calc(env(safe-area-inset-top, 0px) + 16px); align-self:start; display:flex; flex-direction:column; gap:2px; font-size:13px}
nav.index .grp{font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); font-weight:700; margin:12px 0 4px}
nav.index a{color:var(--fg); text-decoration:none; padding:6px 10px; border-radius:6px; display:flex; gap:8px; align-items:baseline}
nav.index a:hover, nav.index a:focus-visible{background:var(--surface); outline:none}
nav.index a b{color:var(--accent); font-size:11px; letter-spacing:.04em; min-width:48px}
main{min-width:0; display:flex; flex-direction:column; gap:28px}
.intro{background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:28px; border-top:5px solid var(--accent)}
.eyebrow{margin:0 0 6px; color:var(--accent); font-size:11.5px; font-weight:700; letter-spacing:.1em; text-transform:uppercase}
h1{margin:0 0 10px; font-size:clamp(28px,4vw,42px); line-height:1.08; letter-spacing:-.02em; text-wrap:balance}
h2{margin:0; font-size:24px; line-height:1.15; letter-spacing:-.01em; text-wrap:balance}
h3{margin:0 0 8px; font-size:15px}
.lead{margin:0; max-width:72ch; color:var(--muted); font-size:15.5px}
.facts{display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; font-size:12.5px}
.facts span{border:1px solid var(--line); background:var(--soft); border-radius:999px; padding:5px 12px}
.legend{display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:8px 18px; margin-top:20px; padding:16px; background:var(--soft); border-radius:10px; font-size:12.5px}
.legend div{display:flex; align-items:center; gap:10px}
.legend svg{flex:none}
table.summary{width:100%; border-collapse:collapse; font-size:13px}
.table-scroll{overflow-x:auto}
table.summary th{text-align:left; font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--line-strong)}
table.summary td{padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top}
table.summary td a{color:var(--fg); font-weight:700; text-decoration:none}
table.summary td a:hover{color:var(--accent)}
.card{background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:24px}
.sig{background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:24px; scroll-margin-top:16px}
.sig-head{display:flex; flex-wrap:wrap; align-items:center; gap:10px 14px; margin-bottom:18px}
.sig-head .eyebrow{width:100%; margin:0}
.chip{font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; border-radius:999px; padding:4px 10px; border:1px solid}
.chip-green{color:var(--green); background:var(--green-bg); border-color:var(--green)}
.chip-amber{color:var(--val-fg); background:var(--flag-bg); border-color:var(--flag-line)}
.chip-grey{color:var(--na-fg); background:var(--na-bg); border-color:var(--na-line)}
.chip-ctx{color:var(--ctx-fg); background:var(--ctx-bg); border-color:var(--ctx-line)}
.sig-body{display:flex; flex-direction:column; gap:20px}
dl.defs{margin:0; display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px 24px; font-size:13.5px}
.def dt{font-size:10.5px; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color:var(--muted); margin-bottom:2px}
.def dd{margin:0}
figure.chart{margin:0; min-width:0}
.chart-scroll svg.flow{max-width:var(--chart-w)}
.chart-scroll{overflow-x:auto; border:1px solid var(--line); border-radius:10px; background:var(--soft); padding:8px}
figcaption{font-size:12.5px; color:var(--muted); margin-top:8px; max-width:80ch}
svg.flow{display:block; width:100%; height:auto; font-family:var(--font)}
.edge{fill:none; stroke:var(--edge); stroke-width:1.4}
.arrowhead{fill:var(--edge)}
.n{stroke-width:1.4}
.dashed{stroke-dasharray:5 4}
.n-start{fill:var(--start-bg); stroke:var(--start-bg)}
.n-step{fill:var(--surface); stroke:var(--line-strong)}
.n-dec{fill:var(--dec-bg); stroke:var(--dec-line)}
.n-cand{fill:var(--cand-bg); stroke:var(--cand-line); stroke-width:2}
.n-flag{fill:var(--flag-bg); stroke:var(--flag-line); stroke-width:1.6}
.n-val{fill:var(--val-bg); stroke:var(--val-line)}
.n-na{fill:var(--na-bg); stroke:var(--na-line)}
.n-out{fill:var(--out-bg); stroke:var(--out-line)}
.n-ctx{fill:var(--ctx-bg); stroke:var(--ctx-line)}
.n-plan{fill:var(--surface); stroke:var(--cand-line)}
.n-trig{fill:var(--trig-bg); stroke:var(--trig-line)}
.n-start.dashed{fill:var(--surface); stroke:var(--fg)}
.nt{fill:var(--fg)}
.nt-start{fill:var(--start-fg)}
.nt .t-main{font-size:12px; font-weight:700}
.nt .t-sub{font-size:10.5px; font-weight:400; opacity:.85}
.nt .t-tag{font-size:9.5px; font-weight:700; letter-spacing:.08em}
.nt-cand .t-tag, .nt-plan .t-tag{fill:var(--cand-fg)}
.nt-cand{fill:var(--cand-fg)}
.nt-val .t-tag, .nt-flag .t-tag{fill:var(--val-fg)}
.nt-na .t-tag, .nt-out .t-tag{fill:var(--na-fg)}
.nt-ctx .t-tag{fill:var(--ctx-fg)}
.nt-trig .t-tag{fill:var(--fg)}
.el{font-size:11px; font-weight:700; fill:var(--muted)}
.el-yes{fill:var(--green)}
.el-no{fill:var(--accent)}
.foot{font-size:12.5px; color:var(--muted)}
a:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
@media (max-width:1100px){ .wrap{grid-template-columns:minmax(0,1fr)} nav.index{position:static; flex-direction:row; flex-wrap:wrap; gap:6px}
  nav.index .grp{width:100%; margin:4px 0 0} nav.index a{background:var(--surface); border:1px solid var(--line)} }
@media print{ nav.index{display:none} .wrap{display:block} .sig{break-before:page; border:none} .chart-scroll{overflow:visible} svg.flow{min-width:0!important} }
@media (prefers-reduced-motion: reduce){ *{scroll-behavior:auto} }
"""


def legend_swatch(cls):
    if cls == 'n-dec':
        shape = '<polygon class="n n-dec" points="6,2 26,2 31,9 26,16 6,16 1,9"/>'
    else:
        rx = 8 if cls == 'n-start' else 3
        shape = f'<rect class="n {cls}" x="1" y="2" width="30" height="14" rx="{rx}"/>'
    return f'<svg width="32" height="18" viewBox="0 0 32 18" aria-hidden="true">{shape}</svg>'


def page():
    nav = ['<nav class="index" aria-label="Signals">', '<span class="grp">Overview</span>', '<a href="#pipeline"><b>All</b>Shared pipeline</a>',
           '<a href="#client-group"><b>All</b>Client group</a>', '<span class="grp">Signals</span>']
    nav += [f'<a href="#{s["id"]}"><b>{s["code"]}</b>{escape(s["name"])}</a>' for s in SECTIONS if s['kind'] != 'Context']
    nav += ['<span class="grp">Context</span>'] + [f'<a href="#{s["id"]}"><b>CTX</b>{escape(s["name"])}</a>' for s in SECTIONS if s['kind'] == 'Context']
    nav.append('</nav>')
    rows = ''.join(f'<tr><td><a href="#{s["id"]}">{escape(s["code"])}</a></td><td>{escape(s["name"])}</td><td>{escape(s["means"])}</td>'
                   f'<td><span class="chip chip-{s["status"][1]}">{escape(s["status"][0])}</span></td></tr>' for s in SECTIONS)
    legend = ''.join(f'<div>{legend_swatch(c)}<span>{escape(t)}</span></div>' for c, t in LEGEND)
    intro = f"""<section class="intro" id="top">
<p class="eyebrow">Bond Radar · DCM internal signals</p>
<h1>How each signal works</h1>
<p class="lead">One flowchart per signal, showing the exact steps the development rules follow, from a source record to a test candidate.
The rules follow the definitions agreed with the DCM team (rule version development-2). Every record ends with one status, and nothing becomes an
alert until the owner of the definition signs it off.</p>
<div class="facts"><span>Rule version development-2</span><span>Applies to every client in the portfolio extracts</span><span>Updated 7 November 2026</span></div>
<div class="legend" aria-label="Legend">{legend}</div>
</section>
<section class="card"><h3>Signals at a glance</h3><div class="table-scroll"><table class="summary"><thead><tr><th>ID</th><th>Signal</th><th>Definition</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></div><p class="foot">The "number of investor sales" signal was dropped by DCM: HSBC initiates the investor interaction, so it is not an independent indicator.</p></section>
<section class="sig" id="pipeline"><header class="sig-head"><p class="eyebrow">All signals</p><h2>Shared pipeline</h2></header>{pipeline()}</section>
<section class="sig" id="client-group"><header class="sig-head"><p class="eyebrow">All signals</p><h2>Client group</h2></header>{identity()}</section>"""
    body = intro + ''.join(section(s) for s in SECTIONS)
    body += ('<p class="foot">Source of truth: development/pvd_client_cohort_lab (engine/bond_radar.py, alignment.py, sig07_crr.py, portfolio.py) and '
             'docs/MEETING_ALIGNMENT_REVIEW.md. Regenerate with python3 docs/signal_flowcharts/build_signal_flowcharts.py.</p>')
    return ('<title>Bond Radar Signal Logic</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            f'<style>{CSS}</style>\n<div class="wrap">{"".join(nav)}<main>{body}</main></div>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(HERE / 'Bond_Radar_Signal_Logic.html'))
    ap.add_argument('--fragment', help='also write the page without the document wrapper (for publishing)')
    a = ap.parse_args()
    content = page()
    Path(a.out).write_text('<!doctype html>\n<html lang="en-GB">\n<head>\n<meta charset="utf-8">\n'
                           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                           + content.replace('</style>\n', '</style>\n</head>\n<body>\n', 1) + '</body>\n</html>\n')
    if a.fragment:
        Path(a.fragment).write_text(content)
    print('Wrote', a.out)


if __name__ == '__main__':
    main()
