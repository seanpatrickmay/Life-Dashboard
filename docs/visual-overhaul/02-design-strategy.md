# Visual Overhaul — Improvement Plan (the Refined-Retro design system)

> The concrete design strategy that the implementation plan (`03-…`) will execute. Direction ratified in `.impeccable.md`: **lush pond kept; UI hardened into a pixel/neo-brutalist system; existing palette solidified (60-30-10, WCAG AA).** Grounded in real `monetTheme.ts` values.

## 0. One-paragraph north star
Every surface becomes **one crafted artifact**: opaque solid fills (no translucency), a **2px ink border**, a **hard offset pixel shadow** (no blur — rewire `shadows.pixel`), **squarer corners** (~6px), `image-rendering: pixelated`, VT323 chrome over legible Space Grotesk body. The lush pond shows **between** cards, not muddily *through* them. One **scarce** accent (pond) earns attention. WCAG AA in light + dark.

## 1. Token architecture (primitive → semantic → component)
Keep the existing `palette` as **primitives** (sky/bloom/pond/ember/lilac/neutral — good bones). Add **darker fill steps** so accents can carry text accessibly:
- `pond['400'] ≈ #2E7568`, `pond['500'] ≈ #1F5A4F` (for accent fills / hover; validate ≥4.5:1 with chosen text).
- (Optionally) `ember['400']`, `bloom['400']` later if status fills need them.

Then a **solid semantic layer** (replaces today's translucent tokens). Proposed starting values — **validated/tuned during implementation via `/colorize` + a contrast check** (never shipped unverified):

| Semantic token | Light (proposed) | Dark (proposed) | Role |
|---|---|---|---|
| `backgroundPage` | `#F5EFE2` (keep) | `#0F1424` (keep) | 60% — pond scene paints over it |
| `surface` (card) | `#FCFAF4` warm paper | `#18213A` panel | 30% — the card body, **opaque** |
| `surfaceRaised` | `#FFFFFF` | `#222C49` | elevation via **lightness step**, not alpha |
| `surfaceInset` | `#EFE7D6` | `#101831` | wells/inputs (a step *down*) |
| `borderStrong` | `#1E1F2E` ink | `#E7E0F0` parchment | the **2px pixel border** (≥3:1 vs surface) |
| `borderSoft` | `#E1D6C8` | `#2F3A5C` | hairline dividers only |
| `shadowPixel` | `4px 4px 0 0 rgba(23,20,33,0.85)` | `4px 4px 0 0 rgba(0,0,0,0.55)` | **hard offset, 0 blur** |
| `textPrimary` | `#1E1F2E` (keep) | `#F6F0E8` (keep) | ≥4.5:1 on surface |
| `textSecondary` | `#595462` (solidified, darker) | `#B9B2C6` | **solid** (kill the rgba 72%), ≥4.5:1 |
| `accent` (fill) | `pond['200']` #7ED7C4 | `pond['200']` #7ED7C4 | **scarce 10%** — CTA / active fills |
| `accentText` | ink `#1E1F2E` | ink `#0F1424` | text *on* accent fills (ink-on-teal ≈ **9.7:1** ✓; white-on-teal would fail) |
| `accentStrong` | `pond['400']` #2E7568 | `pond['100']` #B8F0DF | active **borders** / focus lines / underlines (UI ≥3:1) |
| `focusRing` | `accentStrong` | `accentStrong` | visible 2px focus outline |
| `danger`/`success` | keep ember/pond `300` | keep | status (solid, not subtle-alpha) |

**Elevation rule:** never use `rgba(...,0.04–0.18)` overlay fills for surfaces again. Steps are solid lightness deltas. (Alpha is fine for scrims/focus-glow only.)

## 2. The pixel card (highest-leverage — cascades everywhere)
Restyle the shared `CardShell` (`components/common/Card.tsx`):
- `background: surface` (opaque) · `border: 2px solid borderStrong` · `box-shadow: shadowPixel` (replace `shadows.soft`) · `border-radius: radii.pixel` (**add `radii.pixel: '6px'`**; retire 22px) · keep `image-rendering: pixelated`.
- **Header** in VT323 (`fonts.heading`); body stays Space Grotesk.
- **Halo text-shadow:** remove on opaque cards (it only helped over the painting; it now muddies). Keep halos *only* for text rendered directly over the pond (e.g. the Shell greeting).
- **States:** hover → `translate(-1px,-1px)` + shadow grows to `6px 6px` (the "lift"); active/selected → `borderStrong` becomes `accent` **or** shadow recolors to accent. **All motion behind `prefers-reduced-motion` guards** (the repo already has the pattern).
- **Optional hero treatment:** `frame_corners_{light,dark}` sprites (defined, unused) as corner ornaments on the Brief hero card only — restraint.

## 3. Component primitives (the system)
Extract/standardize so every control speaks the language (`components/common/`):
- **Button** — *primary:* `accent` fill + `accentText` + 2px ink border + `shadowPixel`; **press** = `translate(3px,3px)` + drop shadow (the satisfying neo-brutalist "push"; reduced-motion → just darken). *secondary:* `surface` fill, 2px ink border, ink text. *ghost:* text + underline-on-hover. **Not every button is primary** (hierarchy).
- **Input/Select** — `surfaceInset` fill, 2px ink border, focus = `accent` border + 2px `focusRing` outline. Label in VT323 small-caps optional.
- **Chip/Pill** — compact pixel: 2px border, ~4px radius, solid fill; *active* = `accent` fill + `accentText`.
- **Tabs/Nav** — replace soft underlines with a **pixel shelf**: active tab = `surface` + 2px border + small offset shadow + `accent` baseline; inactive = flat ghost. Bottom-nav active item gets the accent treatment.

## 4. Typography
- **VT323** → headings, section labels, metric numerals, chip/nav labels (chrome). Establish a modular scale (≈1.25): e.g. `display 44 / h1 34 / h2 26 / label 18`. VT323 renders large — set sizes on the integer grid.
- **Space Grotesk** → all body/paragraph/data text, **16px base, 1.5 line-height** — never shrink the pixel font into body copy (legibility + WCAG).
- Tighten letter-spacing on VT323 caps labels; generous line-height on body.

## 5. The pond (keep lush)
- Backdrop stays as-is (the soul). With cards now **opaque**, the pond reads as intended **between/around** cards → compose layouts so the scene peeks in gutters.
- Optional later: a faint `vignetteHaze`/scrim *only behind dense card clusters* if legibility needs it (solid cards likely make this unnecessary). No change to sprites.

## 6. Charts & data viz
Adopt the pixel language: `getStrokePattern` dithered fills under series, 2px pixel gridlines, VT323 axis labels, square (non-rounded) line caps. Cohesion without new chart libs.

## 7. Accessibility gates (hard requirements)
- WCAG **AA both modes**: body/text pairs ≥ 4.5:1, large/UI ≥ 3:1 — validated for `text*` on `surface`/`surfaceRaised`/`surfaceInset` and `accentText` on `accent`.
- Pixel font **never** for body. Decorative sprites/frames `aria-hidden`. Focus rings always visible (`focusRing`, ≥3:1).
- Every hover/press transform gated by `prefers-reduced-motion`.

## 8. Implementation waves (→ becomes the TDD task plan)
1. **Tokens** — extend pond ramp; add solid semantic tokens + `radii.pixel` + tuned `shadowPixel`; `/colorize` + contrast validation. *(theme only; no visual regressions in tests yet)*
2. **Card** — rewire `CardShell` to the pixel system (cascades site-wide). Re-screenshot.
3. **Primitives** — Button / Input / Chip / Tabs pixel components (extract shared; replace ad-hoc usages).
4. **Page sweeps** — Today · Read · Reflect · Body · Settings: remove leftover translucent/`shadows.soft`/22px usages; apply primitives; pond-in-gutters.
5. **Charts** — pixel fills/gridlines/labels.
6. **Polish** — halo re-tune, focus/press states, `frame_corners` on the Brief hero, dark-mode pass, screenshot QA (both modes, mobile + desktop), `tsc` + `vitest` green.

**Sequencing logic:** tokens first (everything depends on them) → Card (one change, broad cascade) → primitives (reused by pages) → pages → charts → polish. Each wave keeps `tsc` + `vitest` green and is independently screenshot-verifiable.
