// Build Bond_Radar_Manager_Briefing.docx from the meeting-pack markdown files,
// using the HSBC / WDAC house style (A4, INTERNAL banner, grey panel headings).
// Usage (from manager_meeting_20261106/): NODE_PATH=<global node_modules> node tools/build_briefing_docx.js
const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, Header, Footer,
        AlignmentType, LevelFormat, BorderStyle, WidthType, ShadingType, HeadingLevel,
        PageNumber, PageBreak, TabStopType } = require('docx');

const ROOT = path.resolve(__dirname, '..');
const FILES = ['02_BRIEFING_ONE_PAGER.md', '01_MEETING_PLAN.md', '03_REQUIREMENTS_SUMMARY.md', '04_SIGNAL_DEFINITIONS.md',
               '05_RESULTS_AND_FINDINGS.md', '06_PRACTICALITY_ASSESSMENT.md', '07_NEXT_STEPS_AND_ROADMAP.md', '08_QUESTIONS_AND_ANSWERS.md'];
const RED = 'DB0011', DKRED = 'A4000C', GREY = 'F3F3F3', LGREY = 'F2F2F2', MID = '757575', SILVER = 'BABABA';
const BODY = 'Univers Next for HSBC Light', HEAD = 'Univers Next for HSBC Medium';
const WIDTH = 9026;

// Status symbols do not render reliably in Word fonts; use words.
const clean = s => s.replace(/✅/g, '[Yes]').replace(/⚠️/g, '[Partial]').replace(/❌/g, '[No]').replace(/⏱/g, '(45 min)')
  .replace(/≥/g, '>=').replace(/≤/g, '<=');

// Inline markdown -> TextRuns: **bold**, *italic*, `code`, [text](link)
function runs(text, base = {}) {
  text = clean(text).replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  const out = [];
  const re = /(\*\*(?:[^*]|`[^`]*`)+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith('**')) out.push(new TextRun({ text: t.slice(2, -2).replace(/`/g, ''), bold: true, ...base }));
    else if (t.startsWith('`')) out.push(new TextRun({ text: t.slice(1, -1), font: 'Consolas', size: base.size ? base.size - 2 : 20, ...Object.fromEntries(Object.entries(base).filter(([k]) => k !== 'font' && k !== 'size')) }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

const border = { style: BorderStyle.SINGLE, size: 4, color: SILVER };
const borders = { top: border, bottom: border, left: border, right: border };

function table(lines) {
  const rows = lines.filter(l => !/^\|\s*-/.test(l)).map(l => l.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim()));
  const n = rows[0].length;
  // Column widths proportional to content length, with a floor so short columns stay readable.
  const lens = Array.from({ length: n }, (_, i) => Math.max(...rows.map(r => Math.min((r[i] || '').length, 90)), 4));
  // Minimum width fits the longest single word in the column (no mid-word breaks at 9pt).
  const words = Array.from({ length: n }, (_, i) => Math.max(...rows.map(r => Math.max(...clean((r[i] || '').replace(/[*`]/g, '')).split(/\s+|<br>/).map(w => w.length)))));
  const total = lens.reduce((a, b) => a + b, 0);
  const mins = words.map(w => Math.max(Math.min(w * 105 + 260, 2600), 700));
  let widths = lens.map((l, i) => Math.max(mins[i], Math.round(WIDTH * l / total)));
  // Shrink only the slack above each column's minimum, so short columns keep whole words.
  const excess = widths.reduce((a, b) => a + b, 0) - WIDTH;
  const slack = widths.map((w, i) => w - mins[i]), slackSum = slack.reduce((a, b) => a + b, 0);
  if (excess > 0 && slackSum > 0) widths = widths.map((w, i) => Math.floor(w - excess * slack[i] / slackSum));
  widths[n - 1] += WIDTH - widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: WIDTH, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, ri) => new TableRow({
      tableHeader: ri === 0, cantSplit: true,
      children: widths.map((w, ci) => new TableCell({
        borders, width: { size: w, type: WidthType.DXA },
        shading: { fill: ri === 0 ? GREY : LGREY, type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: (r[ci] || '').split(/<br>/).map(part => new Paragraph({
          spacing: { after: 40, line: 240 },
          children: runs(part, ri === 0 ? { bold: true, font: HEAD, size: 18 } : { size: 18 }),
        })),
      })),
    })),
  });
}

function convert(md, first) {
  const out = [];
  const lines = md.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    if (line.startsWith('|')) {
      const block = [];
      while (i < lines.length && lines[i].startsWith('|')) block.push(lines[i++]);
      i--;
      out.push(table(block));
      out.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
      continue;
    }
    let m;
    if ((m = /^# (.*)/.exec(line))) out.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, spacing: { before: 120, after: 200 }, children: runs(m[1]) }));
    else if ((m = /^## (.*)/.exec(line))) out.push(new Paragraph({ heading: HeadingLevel.HEADING_4, spacing: { before: 240, after: 120 }, children: runs(m[1]) }));
    else if ((m = /^### (.*)/.exec(line))) out.push(new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 160, after: 80 }, children: runs(m[1], { bold: true }) }));
    else if ((m = /^(\s*)[-*] (.*)/.exec(line))) out.push(new Paragraph({ numbering: { reference: 'hsbc-bullets', level: m[1].length >= 2 ? 1 : 0 }, spacing: { before: 60, after: 60 }, children: runs(m[2]) }));
    else if ((m = /^(\s*)(\d+)\. (.*)/.exec(line))) out.push(new Paragraph({ indent: { left: m[1].length >= 2 ? 1080 : 720, hanging: 360 }, spacing: { before: 60, after: 60 }, children: runs(`${m[2]}.\t${m[3]}`) }));
    else out.push(new Paragraph({ children: runs(line) }));
  }
  return out;
}

const cover = [
  new Paragraph({ spacing: { before: 1200, after: 120 }, children: [new TextRun({ text: 'Bond Radar', font: HEAD, size: 56, color: RED })] }),
  new Paragraph({ spacing: { after: 480 }, children: [new TextRun({ text: 'Results, practicality and next steps — discussion pack', font: BODY, size: 32 })] }),
  table([
    '| Item | Detail |', '|---|---|',
    '| Use case | AI DCM / Use Case 6 – Market Signals (Bond Radar) |',
    '| Meeting | Line-manager review, 6 November 2026 |',
    '| Prepared by | Shadi Nashed |',
    '| Status | Development on three target clients (Vodafone, Siemens Energy, SoftBank); rule version development-2, aligned with DCM meeting decisions |',
    '| Contents | One-page briefing · Meeting plan · Requirements · Signal definitions · Results · Practicality assessment · Next steps · Questions and answers |',
    '| Attachments | Dashboard (HTML), screenshots, signal workbooks, requirements v1.1, alignment review — see the meeting-pack folder |',
  ]),
  new Paragraph({ spacing: { before: 240 }, children: [new TextRun({ text: 'All figures are development evidence; no business trigger is confirmed.', italics: true, color: MID, size: 18 })] }),
];

const body = [];
FILES.forEach(f => body.push(...convert(fs.readFileSync(path.join(ROOT, f), 'utf8'), false)));

const banner = new TextRun({ text: 'INTERNAL', color: MID, font: BODY, size: 16 });
const doc = new Document({
  creator: 'Shadi Nashed', title: 'Bond Radar — manager discussion pack',
  styles: {
    default: { document: { run: { font: BODY, size: 21, language: { value: 'en-GB' } }, paragraph: { spacing: { after: 140, line: 257, lineRule: 'auto' } } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: BODY, size: 32 },
        paragraph: { spacing: { after: 0, line: 240, lineRule: 'auto' },
          border: { top: { style: BorderStyle.SINGLE, size: 48, color: GREY, space: 1 }, bottom: { style: BorderStyle.SINGLE, size: 48, color: GREY, space: 1 } },
          shading: { fill: GREY, type: ShadingType.CLEAR }, outlineLevel: 0 } },
      { id: 'Heading3', name: 'heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: HEAD }, paragraph: { spacing: { line: 240, lineRule: 'auto' }, outlineLevel: 2 } },
      { id: 'Heading4', name: 'heading 4', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: HEAD, color: DKRED, italics: true, size: 24 },
        paragraph: { spacing: { before: 40 }, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: MID, space: 1 } }, outlineLevel: 3 } },
    ],
  },
  numbering: { config: [{ reference: 'hsbc-bullets', levels: [
    { level: 0, format: LevelFormat.BULLET, text: '–', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
    { level: 1, format: LevelFormat.BULLET, text: '○', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
  ] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 2410, right: 1440, bottom: 1440, left: 1440, header: 284, footer: 284 } } },
    headers: { default: new Header({ children: [new Paragraph({ children: [banner] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: WIDTH }],
      children: [new TextRun({ text: 'INTERNAL', color: MID, font: BODY, size: 16 }),
                 new TextRun({ text: '\tBond Radar — manager discussion pack · page ', color: MID, font: BODY, size: 16 }),
                 new TextRun({ children: [PageNumber.CURRENT], color: MID, font: BODY, size: 16 })] })] }) },
    children: [...cover, ...body],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(path.join(ROOT, 'Bond_Radar_Manager_Briefing.docx'), buf);
  console.log('Wrote Bond_Radar_Manager_Briefing.docx', buf.length, 'bytes');
});
