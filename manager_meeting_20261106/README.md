# Manager meeting pack — Bond Radar (6 November 2026)

Discussion pack for reviewing the Bond Radar results and development with your line manager, and for deciding whether, and how, to build the board for DCM users.

## Start here

| Order | File | Use in the meeting |
|---|---|---|
| 1 | **`01_MEETING_PLAN.md`** | Agenda, talking points, demo script, decisions to ask for, notes table |
| 2 | **`02_BRIEFING_ONE_PAGER.md`** | One page to hand over or share on screen |
| — | **`Bond_Radar_Manager_Briefing.docx`** / `.pdf` | The whole pack (files 01–08) as one HSBC-style document (24 pages) for printing or sending |
| 3 | `03_REQUIREMENTS_SUMMARY.md` | Dashboard and signal requirements with status (DASH01–07, SIG01–07) |
| 4 | `04_SIGNAL_DEFINITIONS.md` | The agreed definitions on one page |
| 5 | `05_RESULTS_AND_FINDINGS.md` | Results by client, the SoftBank example and key findings |
| 6 | **`06_PRACTICALITY_ASSESSMENT.md`** | Feasibility by signal, cost drivers, options, recommendation, considerations, risks |
| 7 | **`07_NEXT_STEPS_AND_ROADMAP.md`** | Two-week actions with owners; Phase 1–3 roadmap |
| 8 | `08_QUESTIONS_AND_ANSWERS.md` | Likely manager questions with suggested answers |

## Attachments

| Folder | Contents |
|---|---|
| `attachments/dashboard/` | `dcm_signals_dashboard.html` (open in any browser, works offline); `screenshots/` as a backup for the demo |
| `attachments/reports/` | `SIGNAL_OVERVIEW.xlsx` and 8 signal/context workbooks, `SIGNAL_DEFINITIONS.md`, `FINDINGS_AND_LIMITATIONS.md`, `RUN_REVIEW.md`, `owner_review/` (44 owner questions, coverage) |
| `attachments/requirements/` | `Bond Radar Requirements.docx` / `.md` (v1.1) and `MEETING_ALIGNMENT_REVIEW.md` (meeting requirements vs development) |

## The message in three lines

1. **It works.** The engine and board run end to end on real data, follow the DCM definitions, and every number traces back to its source.
2. **Data is the constraint.** One signal is live today (9 new-facility approvals). SIG01 is one data field (LoanIQ drawn amount) away from working. The strongest example is SoftBank: a new USD 400m facility approved 17 Sep with USD 179.7m already drawn.
3. **Recommendation:** a phased pilot (20–30 clients, 3–5 bankers, weekly) plus a back-test against past deals. It needs sponsorship for the data requests and the CME governance review.

*All figures are development evidence for three target clients (core assessment 3 Nov 2026). No business trigger is confirmed.*

## Regenerating the Word / PDF briefing

The Word document is built from files 01–08 so the two never drift:

```sh
cd manager_meeting_20261106
NODE_PATH=$(npm root -g) node tools/build_briefing_docx.js   # needs the docx npm package
soffice --headless --convert-to pdf Bond_Radar_Manager_Briefing.docx
```
