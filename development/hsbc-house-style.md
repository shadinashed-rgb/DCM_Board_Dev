# HSBC house style — theme module (optional, swappable)

This is the **default house style** for dashboards built for HSBC stakeholders, captured as a reusable
theme. It lives in the **application/theming layer**, not the platform core: the platform and the build
patterns are brand-agnostic, and this theme is one concrete skin. **To build for another brand, swap
the tokens in §1 and keep everything else.** Nothing in the architecture depends on these values.

Tokens and component styles here are `[observed]` in the reference HSBC boards (M&A screening, Client
Signals, the extraction dashboard).

---

## 1. Design tokens (the one thing you swap to re-theme)
```css
:root{
  /* brand */
  --hsbc-red:#db0011; --hsbc-red-dark:#b1000e;
  /* neutrals */
  --hsbc-black:#000; --hsbc-charcoal:#333; --hsbc-slate:#5c5c5c;
  --hsbc-border:#d7d7d7; --hsbc-border-strong:#b8b8b8;
  --hsbc-bg:#f3f3f3; --hsbc-card:#fff; --hsbc-soft:#f8f8f8;
  /* status fills + text (used for cells, pills, banners) */
  --pill-red-bg:#fde7ea;  --pill-red-tx:#8f0010;
  --pill-amber-bg:#fff2db; --pill-amber-tx:#7a5500;
  --pill-green-bg:#e7f5ec; --pill-green-tx:#1c5c35;
  --pill-grey-bg:#efefef;  --pill-grey-tx:#666;
  /* elevation + shape */
  --shadow:0 8px 24px rgba(0,0,0,.06); --radius:14px;
}
```
Only `--hsbc-red`/`--hsbc-red-dark` and the status fills are truly brand-specific; the neutrals and
shape are a clean corporate baseline that re-skins easily.

## 2. Typography
- Primary face: **`"Univers Next for HSBC"`** with fallback `Arial, sans-serif`. The brand font is
  rarely web-available, so the Arial fallback is what most environments render — design for it.
- Weights: 700 for titles, labels, table headers, buttons; 400 body. Antialiased
  (`-webkit-font-smoothing:antialiased`).
- Eyebrow/kicker labels: 11–12px, 700, uppercase, `letter-spacing:.08em`, in `--hsbc-red`.
- Titles: 18px desk title; large hero numerals where used. Body: 13–14px, line-height ~1.5.
- A monospace face is fine for code/IDs/endpoints (e.g. `SFMono-Regular, Consolas, monospace`).

## 3. Colour convention — important
Red is the **brand colour and the "strongest signal,"** *not* an error/danger colour. The observed
status scale, strongest → weakest, is **red → amber → green → grey(no data)**, encoded as cell codes
`r / a / g / n`. This is deliberately the inverse of the usual traffic-light "red = bad." **Always
document the meaning per board**, because it surprises people. If a board needs a genuine error state,
use wording/iconography rather than relying on red alone.

## 4. Logo & iconography
- Logo and favicon were served from `/studio/studio/static/ui/` on the Studio host
  `aimarkets-studio.hc.cloud.uk.hsbc` (`logo_hsbc.png`, `hsbc_icon.ico`). **[observed]**
- For portability (and so a frozen/offline file still shows the mark), prefer an **inline base64** logo
  over a path that only resolves inside Studio.
- `<meta name="theme-color" content="#db0011">`.

## 5. Layout
- **Page**: centered, `max-width` ~1300–1600px, `padding:24px` (14px on mobile), background `--hsbc-bg`.
- **Card**: `--hsbc-card` background, `1px solid --hsbc-border`, `border-radius:14–16px`, `--shadow`.
- **Topbar**: a card with a left identity block (red kicker + black title) and right-aligned actions +
  status; wraps on small screens.
- **Panels/sections**: cards with 16–24px padding and 20px vertical rhythm between them.
- An accent device seen on hero/notes cards: a 6px `--hsbc-red` top border.

## 6. Components
- **Buttons** — pill shape (`border-radius:999px`), 700 uppercase 11px, `.08em` tracking.
  Primary = solid `--hsbc-red` (hover `--hsbc-red-dark`); secondary = white with red text/border.
  Disabled = reduced opacity, `cursor:not-allowed`.
- **Status pills** — small text with a tone attribute driving colour: neutral, `busy` (amber `#996300`),
  `success` (green `#1c5c35`), `error` (red). Used for every async action.
- **Meta pills** — bordered uppercase chips for tags/counts; a `priority` variant is solid red.
- **Inline status chips** — rounded chips with `busy/success/error` fills from the status palette.
- **Progress bar** — 10px track, fill `linear-gradient(90deg,#db0011,#ff6b77)`.
- **Tables** — black (`#111`) header row, white bold uppercase header text; bordered cells; zebra rows
  on `--hsbc-soft`; horizontal scroll wrapper for wide tables.
- **Coloured signal cell** (optional pattern) — rounded chip tinted by the `r/a/g/n` status palette.
- **Drill-down / notes cards** — soft-bg bordered blocks; red eyebrow label + body.

## 7. Accessibility & responsiveness
- Maintain visible keyboard focus (don't remove outlines without a replacement).
- Check contrast for tinted status text on its fill (the `--pill-*-tx` on `--pill-*-bg` pairs pass).
- Respect `prefers-reduced-motion` for any animation.
- Responsive breakpoints around 1200px (collapse multi-column to single) and 720px (compact padding,
  stack actions, full-width selects).

## 8. Re-theming for another brand (keep it general)
1. Replace `--hsbc-red`/`--hsbc-red-dark` with the brand primary; adjust the four status fill/text pairs
   if the brand needs different semantics.
2. Swap the font stack and the logo (inline base64).
3. Decide and **document** the colour convention (keep red-as-strongest, or move to conventional
   traffic-light — but state it on the board).
4. Leave layout, components, and all platform plumbing unchanged. The architecture is brand-agnostic;
   only this token layer is HSBC-specific.

## 9. Paste-ready minimal theme block
```css
:root{
  --brand:#db0011; --brand-dark:#b1000e;
  --ink:#000; --charcoal:#333; --slate:#5c5c5c;
  --border:#d7d7d7; --border-strong:#b8b8b8; --bg:#f3f3f3; --card:#fff; --soft:#f8f8f8;
  --pill-red-bg:#fde7ea; --pill-red-tx:#8f0010; --pill-amber-bg:#fff2db; --pill-amber-tx:#7a5500;
  --pill-green-bg:#e7f5ec; --pill-green-tx:#1c5c35; --pill-grey-bg:#efefef; --pill-grey-tx:#666;
  --shadow:0 8px 24px rgba(0,0,0,.06); --radius:14px;
  --font:"Univers Next for HSBC", Arial, sans-serif;
}
/* re-theme: change --brand/--brand-dark, --font, the logo, and document the colour convention */
```
