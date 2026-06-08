# Visual Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Plan location note:** kept in `docs/visual-overhaul/` (with the initiative's research/critique/strategy) rather than the default `docs/superpowers/plans/`, by user-preference cohesion.

**Goal:** Harden the Life-Dashboard UI into a cohesive pixel / neo-brutalist system — solid principled colour (60-30-10, WCAG AA), thick ink borders, hard offset shadows, squarer corners, VT323 chrome — over the kept lush pixel-art pond.

**Architecture:** Token-first. Solidify `monetTheme.ts` (opaque semantic tokens + a WCAG-enforcing contrast test) → rewire the shared `CardShell` (one change, site-wide cascade) → build pixel primitives (Button/Input/Chip/Tabs) → sweep pages to use them → pixel-ify charts → polish. Each wave keeps `tsc` + `vitest` green and is screenshot-verifiable.

**Tech Stack:** React + TypeScript + **styled-components** (NOT Tailwind — follow the project's actual stack) + Vitest + Recharts. Theme via `ThemeProvider` (`lightTheme`/`darkTheme` in `frontend/src/theme/monetTheme.ts`).

**Testing reality:** Pixel *appearance* isn't unit-testable. The TDD anchors are: (1) a **contrast matrix** that enforces the colour system, (2) token-shape/opacity tests, (3) component structural + accessibility + reduced-motion tests. Visual appearance is verified by **screenshots** (both modes, mobile + desktop) at the PR step.

**Run all commands from `frontend/`.** Test: `npx vitest run <path>`. Typecheck: `npx tsc --noEmit`.

---

## WAVE 1 — Tokens & the colour contract

### Task 1: WCAG contrast utility + AA test matrix (write the contract FIRST)

**Files:**
- Create: `frontend/src/theme/contrast.ts`
- Test: `frontend/src/theme/contrast.test.ts`

- [ ] **Step 1: Write the failing test** (`contrast.test.ts`)

```ts
import { describe, it, expect } from 'vitest';
import { contrastRatio, relativeLuminance } from './contrast';

describe('contrastRatio', () => {
  it('black on white is 21:1', () => {
    expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 0);
  });
  it('white on white is 1:1', () => {
    expect(contrastRatio('#FFFFFF', '#FFFFFF')).toBeCloseTo(1, 1);
  });
  it('is order-independent', () => {
    expect(contrastRatio('#1E1F2E', '#FCFAF4')).toBeCloseTo(contrastRatio('#FCFAF4', '#1E1F2E'), 5);
  });
  it('relativeLuminance of white is ~1', () => {
    expect(relativeLuminance('#FFFFFF')).toBeCloseTo(1, 2);
  });
});
```

- [ ] **Step 2: Run it, verify it fails**

Run: `npx vitest run src/theme/contrast.test.ts`
Expected: FAIL — `contrast.ts` does not exist.

- [ ] **Step 3: Implement `contrast.ts`**

```ts
// WCAG 2.x relative luminance + contrast ratio. Hex only (#RGB or #RRGGBB).
export function relativeLuminance(hex: string): number {
  const c = hex.replace('#', '');
  const full = c.length === 3 ? c.split('').map((ch) => ch + ch).join('') : c;
  const channels = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
  const lin = channels.map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

export function contrastRatio(fg: string, bg: string): number {
  const l1 = relativeLuminance(fg);
  const l2 = relativeLuminance(bg);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}
```

- [ ] **Step 4: Run it, verify it passes**

Run: `npx vitest run src/theme/contrast.test.ts` → Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/theme/contrast.ts src/theme/contrast.test.ts
git commit -m "feat(visual): WCAG contrast utility for the colour contract"
```

---

### Task 2: Solid semantic tokens + extended pond ramp + the enforcing matrix

**Files:**
- Modify: `frontend/src/theme/monetTheme.ts` (`palette`, `base.radii`, `base.shadows`, `lightTheme.colors`, `darkTheme.colors`)
- Test: `frontend/src/theme/tokens.test.ts` (create)

- [ ] **Step 1: Write the failing test** (`tokens.test.ts`) — encodes the whole contract

```ts
import { describe, it, expect } from 'vitest';
import { lightTheme, darkTheme } from './monetTheme';
import { contrastRatio } from './contrast';

const HEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const themes = [lightTheme, darkTheme] as const;

describe('solid semantic tokens', () => {
  for (const t of themes) {
    const c = t.colors as Record<string, string>;
    it(`${t.mode}: surfaces are opaque hex (no translucency)`, () => {
      for (const key of ['surface', 'surfaceRaised', 'surfaceInset', 'borderStrong', 'borderSoft', 'textPrimary', 'textSecondary', 'accent', 'accentText', 'accentStrong']) {
        expect(c[key], `${key} must exist`).toBeDefined();
        expect(c[key], `${key}=${c[key]} must be opaque hex`).toMatch(HEX);
      }
    });
    it(`${t.mode}: radii.pixel is squarer than the old 22px`, () => {
      expect(parseInt(t.radii.pixel, 10)).toBeLessThanOrEqual(8);
    });
    it(`${t.mode}: shadowPixel is a hard offset (0 blur)`, () => {
      // hard pixel shadow: "<x> <y> 0 0 <color>" — third value (blur) must be 0
      expect(t.shadows.pixel).toMatch(/\b\d+px\s+\d+px\s+0\b/);
    });
  }
});

describe('WCAG AA contrast matrix', () => {
  const pairs: Array<[string, string, number]> = [
    ['textPrimary', 'surface', 4.5],
    ['textSecondary', 'surface', 4.5],
    ['textPrimary', 'surfaceRaised', 4.5],
    ['textPrimary', 'surfaceInset', 4.5],
    ['borderStrong', 'surface', 3.0],
    ['accentText', 'accent', 4.5],
    ['accentStrong', 'surface', 3.0],
  ];
  for (const t of themes) {
    const c = t.colors as Record<string, string>;
    for (const [fg, bg, min] of pairs) {
      it(`${t.mode}: ${fg} on ${bg} >= ${min}:1`, () => {
        expect(contrastRatio(c[fg], c[bg])).toBeGreaterThanOrEqual(min);
      });
    }
  }
});
```

- [ ] **Step 2: Run it, verify it fails**

Run: `npx vitest run src/theme/tokens.test.ts`
Expected: FAIL — `surface`, `radii.pixel`, etc. undefined.

- [ ] **Step 3: Implement the token changes** in `monetTheme.ts`

(a) Extend `palette.pond` (line ~114) with accessible fill steps:
```ts
  pond: { '100': '#B8F0DF', '200': '#7ED7C4', '300': '#3F9B8A', '400': '#2E7568', '500': '#1F5A4F' },
```

(b) In `base` (line ~611), change `radii` and `shadows`:
```ts
  radii: {
    card: '6px',
    shell: '8px',
    pixel: '6px'
  },
  shadows: {
    soft: '0 18px 34px rgba(28, 41, 64, 0.18)', // retained for legacy refs during migration
    pixel: '4px 4px 0 0 rgba(23, 20, 33, 0.85)',
    pixelDark: '4px 4px 0 0 rgba(0, 0, 0, 0.55)'
  },
```

(c) Replace `lightTheme.colors` translucent surface tokens (lines ~628-647) with solids + new tokens:
```ts
    backgroundPage: '#F5EFE2',
    backgroundCard: '#FCFAF4',
    surface: '#FCFAF4',
    surfaceRaised: '#FFFFFF',
    surfaceInset: '#EFE7D6',
    textPrimary: '#1E1F2E',
    textSecondary: '#595462',
    borderStrong: '#1E1F2E',
    borderSoft: '#E1D6C8',
    borderSubtle: '#E1D6C8',          // keep name for legacy refs; now solid
    grid: '#E1D6C8',
    overlay: '#EFE7D6',
    overlayHover: '#E6DBC8',
    overlayActive: '#DCCFB8',
    accent: palette.pond['200'],
    accentText: '#1E1F2E',
    accentStrong: palette.pond['400'],
    accentSubtle: '#E4F4EF',
    danger: palette.ember['300'],
    dangerSubtle: '#FBE6D3',
    success: palette.pond['300'],
    successSubtle: '#DFF1EC',
    focusRing: palette.pond['400'],
    scrollThumb: '#C9BBA6',
    scrollTrack: 'transparent'
```

(d) Replace `darkTheme.colors` (lines ~666-686) likewise:
```ts
    backgroundPage: palette.sky['900'],
    backgroundCard: '#18213A',
    surface: '#18213A',
    surfaceRaised: '#222C49',
    surfaceInset: '#101831',
    textPrimary: '#F6F0E8',
    textSecondary: '#B9B2C6',
    borderStrong: '#E7E0F0',
    borderSoft: '#2F3A5C',
    borderSubtle: '#2F3A5C',
    grid: '#2F3A5C',
    overlay: '#222C49',
    overlayHover: '#2A3656',
    overlayActive: '#33416A',
    accent: palette.pond['200'],
    accentText: '#0F1424',
    accentStrong: palette.pond['100'],
    accentSubtle: '#1C3A39',
    danger: palette.ember['200'],
    dangerSubtle: '#3A2E1E',
    success: palette.pond['100'],
    successSubtle: '#173A36',
    focusRing: palette.pond['100'],
    scrollThumb: '#33416A',
    scrollTrack: 'transparent'
```

> **Note for implementer:** `backgroundCard`/`borderSubtle`/`overlay*` names are KEPT (now solid) so existing component references don't break in this task — they're migrated to the new names during the page sweeps (Wave 4). Do not delete them yet.

- [ ] **Step 4: Run the matrix, verify PASS**

Run: `npx vitest run src/theme/tokens.test.ts`
Expected: PASS. **If any contrast assertion fails, adjust that token darker/lighter until it passes — do not weaken the test.**

- [ ] **Step 5: Typecheck + full theme-consumer smoke**

Run: `npx tsc --noEmit` → Expected: clean (new optional tokens added; existing names retained).

- [ ] **Step 6: Commit**

```bash
git add src/theme/monetTheme.ts src/theme/tokens.test.ts
git commit -m "feat(visual): solid principled semantic tokens + WCAG-AA contrast matrix"
```

---

## WAVE 2 — The pixel card

### Task 3: Rewire `CardShell` to the pixel system

**Files:**
- Modify: `frontend/src/components/common/Card.tsx`
- Test: `frontend/src/components/common/Card.test.tsx` (create or extend)

- [ ] **Step 1: Read** `frontend/src/components/common/Card.tsx` fully to capture current props (`elevated`, `interactive`, halo usage, the `::before` radial glow) before editing.

- [ ] **Step 2: Write the failing test** (`Card.test.tsx`) — structural + a11y, not pixels

```tsx
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import { lightTheme } from '../../theme/monetTheme';
import { Card } from './Card';

const theme = { ...lightTheme, intensity: 'rich', motion: true, moment: 'noon', featureScene: 'auto', willowEnabled: true, sceneDensity: 'lush', sceneHorizon: 0.7, horizonMode: 'auto' } as never;

describe('Card (pixel system)', () => {
  it('renders an opaque surface, thick border, and hard pixel shadow', () => {
    const { container } = render(
      <ThemeProvider theme={theme}><Card data-testid="c">body</Card></ThemeProvider>
    );
    const el = container.querySelector('[data-testid="c"]') as HTMLElement;
    const cs = getComputedStyle(el);
    // styled-components injects real CSS in jsdom; assert the pixel signature
    expect(cs.borderTopWidth).toBe('2px');
    expect(cs.boxShadow).toContain('0px'); // hard offset includes a 0 blur term
    expect(cs.backgroundColor).not.toContain('rgba'); // opaque
  });
});
```

> If `getComputedStyle` proves unreliable in jsdom for styled-components, fall back to asserting the styled component receives `theme.colors.surface`/`theme.shadows.pixel` via a snapshot of `element.className` + `expect(document.head.innerHTML).toContain('2px solid')`. Keep the *intent*: opaque fill, 2px border, hard shadow.

- [ ] **Step 3: Run it, verify it fails** — `npx vitest run src/components/common/Card.test.tsx`

- [ ] **Step 4: Edit `CardShell`** — apply the pixel signature:
  - `background: ${({ theme }) => theme.colors.surface};` (was `backgroundCard` translucent)
  - `border: 2px solid ${({ theme }) => theme.colors.borderStrong};` (was `1px borderSubtle`)
  - `border-radius: ${({ theme }) => theme.radii.pixel};` (was `radii.card` 22px)
  - `box-shadow: ${({ theme }) => (theme.mode === 'dark' ? theme.shadows.pixelDark : theme.shadows.pixel)};` (was `shadows.soft`)
  - Keep `image-rendering: pixelated;`
  - **Remove** the halo `text-shadow` on card content and the radial-gradient `::before` soft glow (they fight the opaque surface). Keep halos only in `Shell`/greeting (over the pond).
  - `interactive`/hover: `&:hover { transform: translate(-1px,-1px); box-shadow: 6px 6px 0 0 <ink/dark>; }` wrapped in `@media (prefers-reduced-motion: no-preference)`.
  - `elevated` → use `surfaceRaised`.

- [ ] **Step 5: Run Card test + the broad consumer suite** — `npx vitest run src/components/common/Card.test.tsx` then `npx vitest run` (whole suite) to catch cascade regressions. Expected: PASS / no new failures.

- [ ] **Step 6: Typecheck** — `npx tsc --noEmit` → clean.

- [ ] **Step 7: Commit** — `git add src/components/common/Card.tsx src/components/common/Card.test.tsx && git commit -m "feat(visual): pixel-neo-brutalist CardShell (solid fill, 2px ink border, hard shadow)"`

---

## WAVE 3 — Pixel primitives

### Task 4: `PixelButton` (primary / secondary / ghost + press state)

**Files:**
- Create: `frontend/src/components/common/PixelButton.tsx`
- Test: `frontend/src/components/common/PixelButton.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import { lightTheme } from '../../theme/monetTheme';
import { PixelButton } from './PixelButton';

const theme = { ...lightTheme, intensity: 'rich', motion: true, moment: 'noon', featureScene: 'auto', willowEnabled: true, sceneDensity: 'lush', sceneHorizon: 0.7, horizonMode: 'auto' } as never;
const wrap = (ui: React.ReactNode) => render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);

describe('PixelButton', () => {
  it('renders children and fires onClick', () => {
    const onClick = vi.fn();
    wrap(<PixelButton onClick={onClick}>Go</PixelButton>);
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(onClick).toHaveBeenCalledOnce();
  });
  it('supports variant and disabled', () => {
    wrap(<PixelButton variant="ghost" disabled>X</PixelButton>);
    expect(screen.getByRole('button', { name: 'X' })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run it, verify it fails** — `npx vitest run src/components/common/PixelButton.test.tsx`

- [ ] **Step 3: Implement `PixelButton.tsx`**

```tsx
import styled, { css } from 'styled-components';

type Variant = 'primary' | 'secondary' | 'ghost';

const variants = {
  primary: css`
    background: ${({ theme }) => theme.colors.accent};
    color: ${({ theme }) => theme.colors.accentText};
    border: 2px solid ${({ theme }) => theme.colors.borderStrong};
    box-shadow: 3px 3px 0 0 ${({ theme }) => theme.colors.borderStrong};
  `,
  secondary: css`
    background: ${({ theme }) => theme.colors.surface};
    color: ${({ theme }) => theme.colors.textPrimary};
    border: 2px solid ${({ theme }) => theme.colors.borderStrong};
    box-shadow: 3px 3px 0 0 ${({ theme }) => theme.colors.borderStrong};
  `,
  ghost: css`
    background: transparent;
    color: ${({ theme }) => theme.colors.textPrimary};
    border: 2px solid transparent;
    box-shadow: none;
    text-decoration: underline transparent;
    &:hover { text-decoration-color: currentColor; }
  `
};

export const PixelButton = styled.button<{ variant?: Variant }>`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 18px;
  letter-spacing: 0.04em;
  padding: 8px 16px;
  border-radius: ${({ theme }) => theme.radii.pixel};
  image-rendering: pixelated;
  cursor: pointer;
  transition: none;
  ${({ variant = 'primary' }) => variants[variant]}
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
  &:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }
  @media (prefers-reduced-motion: no-preference) {
    transition: transform 80ms ease-out, box-shadow 80ms ease-out;
    &:not(:disabled):active { transform: translate(3px, 3px); box-shadow: 0 0 0 0 transparent; }
  }
  @media (prefers-reduced-motion: reduce) {
    &:not(:disabled):active { filter: brightness(0.92); }
  }
`;
```

- [ ] **Step 4: Run it, verify it passes** — `npx vitest run src/components/common/PixelButton.test.tsx`

- [ ] **Step 5: Commit** — `git add src/components/common/PixelButton.tsx src/components/common/PixelButton.test.tsx && git commit -m "feat(visual): PixelButton primitive (neo-brutalist press, reduced-motion safe)"`

---

### Task 5: `PixelField` (input/select) + `PixelChip`

**Files:**
- Create: `frontend/src/components/common/PixelField.tsx`, `frontend/src/components/common/PixelChip.tsx`
- Test: `frontend/src/components/common/PixelField.test.tsx`

- [ ] **Step 1: Write failing test** — render `PixelField` as `<input>`, assert `aria-label` passthrough + value change via `fireEvent.change`; render `PixelChip` with `active` prop, assert it renders children and toggles an `aria-pressed` attr.
- [ ] **Step 2: Verify fail** — `npx vitest run src/components/common/PixelField.test.tsx`
- [ ] **Step 3: Implement**:
  - `PixelField`: styled `input`/`select` — `background: surfaceInset; border: 2px solid borderStrong; border-radius: radii.pixel; color: textPrimary; padding: 8px 12px;` focus → `border-color: accentStrong; outline: 2px solid focusRing; outline-offset: 1px;`
  - `PixelChip`: styled `button` — compact (`padding: 4px 10px; border-radius: 4px; border: 2px solid borderStrong; font: VT323 14px;`); `active` → `background: accent; color: accentText;` else `background: surface; color: textPrimary;` set `aria-pressed={active}`.
- [ ] **Step 4: Verify pass** — `npx vitest run src/components/common/PixelField.test.tsx`
- [ ] **Step 5: Commit** — `git add src/components/common/PixelField.tsx src/components/common/PixelChip.tsx src/components/common/PixelField.test.tsx && git commit -m "feat(visual): PixelField + PixelChip primitives"`

---

### Task 6: Pixel tabs/nav treatment

**Files:**
- Modify: the nav/tab components — `frontend/src/components/**` (locate via `grep -rl "border-bottom" src/components` and the bottom-nav/tablist components touched in the rework: Body sub-nav tablist, bottom-nav).
- Test: extend the relevant existing nav test, or add a structural test asserting the active item gets `aria-current`/active styling.

- [ ] **Step 1:** `grep -rn "aria-selected\|role=\"tab\"\|NavLink" frontend/src/components frontend/src/pages` to enumerate nav/tab sites.
- [ ] **Step 2: Write/extend failing test** — assert active tab has the pixel-shelf marker (e.g. a `data-active` attr or `aria-current="page"`).
- [ ] **Step 3: Implement** — active tab: `background: surface; border: 2px solid borderStrong; border-radius: radii.pixel radii.pixel 0 0; box-shadow: 2px 2px 0 0 borderStrong; border-bottom: 2px solid accentStrong;` inactive: ghost (transparent, `textSecondary`). Bottom-nav active item: `color: accentStrong` + 2px top border.
- [ ] **Step 4: Verify pass** + `npx vitest run` (suite) for regressions.
- [ ] **Step 5: Commit** — `git commit -m "feat(visual): pixel-shelf tabs + active nav treatment"`

---

## WAVE 4 — Page sweeps (apply primitives; remove leftover translucency)

> **Shared procedure per page** (mechanical; verified by `npx tsc --noEmit`, `npx vitest run`, and screenshots):
> 1. `grep -rn "shadows.soft\|radii.card\|rgba(\|borderSubtle\|overlay\b" <page-dir>` to find leftovers.
> 2. Replace: `shadows.soft`→`shadows.pixel`/`pixelDark`; `radii.card`→`radii.pixel`; translucent `rgba(...)` surface fills → `surface`/`surfaceRaised`/`surfaceInset`; `borderSubtle`→`borderStrong` (2px) for emphasis or `borderSoft` (1px) for dividers; ad-hoc `<button>`→`PixelButton`; ad-hoc inputs→`PixelField`; filter pills→`PixelChip`.
> 3. Ensure cards use `CardShell` (no bespoke translucent panels).
> 4. Compose layouts so the pond shows in gutters between cards.
> 5. `npx tsc --noEmit` + `npx vitest run` green; commit per page.

### Task 7: **Today** sweep — `frontend/src/pages/Today.tsx` + Today widgets (Brief hero, summary chips, project quick-capture, readiness widget).
- [ ] Apply shared procedure. Brief hero = the one card permitted the `frame_corners` ornament (added in Wave 6). Summary chips → `PixelChip`. Quick-capture input → `PixelField`, submit → `PixelButton`. Commit: `style(visual): Today page pixel sweep`.

### Task 8: **Read** sweep — `frontend/src/pages/Read.tsx` + `CategoryStrip`, `AIDevSection`, `TuneDrawer`, article cards.
- [ ] Apply shared procedure. CategoryStrip pills → `PixelChip`. TuneDrawer boost/mute controls → `PixelChip`/`PixelButton`. AIDevSection entry card → `CardShell`. Commit: `style(visual): Read page pixel sweep`.

### Task 9: **Reflect** sweep — `frontend/src/pages/Reflect.tsx` + `JournalBook`, QuickCapture, save→Reflect nudge.
- [ ] Apply shared procedure. Journal entry surfaces → `surface`/`surfaceInset`; save button → `PixelButton`. Preserve the reduced-motion guards already added. Commit: `style(visual): Reflect page pixel sweep`.

### Task 10: **Body** sweep — `frontend/src/pages/Body.tsx` + Insights, NutritionContent, the Health|Nutrition tablist.
- [ ] Apply shared procedure + Task 6 tab treatment for the sub-nav. Macro labels/cards → `CardShell` + tokens. Commit: `style(visual): Body page pixel sweep`.

### Task 11: **Settings** + shared chrome sweep — Settings drawer, `Shell` chrome, `MovedBanner`, drawers (`CalendarDetailDrawer`, etc.).
- [ ] Apply shared procedure. Drawer surfaces → `surface`; primary/secondary actions → `PixelButton`. Keep greeting halo (over pond). Commit: `style(visual): Settings + shared chrome pixel sweep`.

---

## WAVE 5 — Charts

### Task 12: Pixel-ify Recharts (Insights/Body charts)
**Files:** chart components under `frontend/src/components/**` (locate via `grep -rln "recharts" src`).
- [ ] **Step 1:** Identify chart files. **Step 2:** No new test (visual); guard with `npx tsc --noEmit` + existing chart tests. **Step 3:** Apply: `strokeWidth={2}`, `strokeLinecap="square"`, dithered `fill` via `getStrokePattern` pattern defs, VT323 tick labels (`tick={{ fontFamily: ... }}`), 2px gridlines using `colors.grid`. **Step 4:** `npx vitest run` green. **Step 5:** Commit `style(visual): pixel-art chart treatment`.

---

## WAVE 6 — Polish & QA

### Task 13: Hero ornament + focus/halo audit + dark-mode pass
- [ ] Add `frame_corners_{light,dark}` (decorative, `aria-hidden`) to the **Brief hero card only**. Audit all `:focus-visible` rings use `focusRing`. Remove any remaining card halos; confirm greeting halo intact. Toggle dark mode + each moment; eyeball contrast. `npx tsc --noEmit` + `npx vitest run` green. Commit `polish(visual): hero ornament, focus rings, dark-mode pass`.

### Task 14: Screenshot QA (the visual gate)
- [ ] Per the repo `pr-screenshots` rule: ensure `playwright` installed in `frontend/`; start dev server; run `node ~/.claude/scripts/screenshot.mjs --port 5173 /today /read /reflect /body /settings` for **light + dark** (toggle), mobile + desktop viewports. Read each screenshot with the Read tool; verify: opaque cards, 2px ink borders, hard offset shadows, squarer corners, pond visible in gutters, legible body text, no translucent glass. Fix any regressions. Save to `/tmp/claude/screenshots/`.

---

## Final review & handoff
- [ ] Dispatch a final code-quality reviewer over the whole diff.
- [ ] `npx tsc --noEmit` (0 errors) + `npx vitest run` (all green) + the contrast matrix green.
- [ ] Use **superpowers:finishing-a-development-branch** → push + open PR with screenshots (both modes).

## Self-review against the strategy (`02-design-strategy.md`)
- ✅ Solid tokens + 60-30-10 + scarce accent → Tasks 2 (+ enforced by contrast matrix).
- ✅ Pixel card (fill/border/shadow/radius) → Task 3.
- ✅ Primitives (Button/Field/Chip/Tabs) → Tasks 4–6.
- ✅ Page sweeps → Tasks 7–11. ✅ Charts → Task 12. ✅ Halo re-tune / hero / focus → Task 13.
- ✅ WCAG AA both modes → contrast matrix (Task 2) + Task 13 audit. ✅ Reduced-motion → Tasks 3,4. ✅ Keep pond lush → unchanged sprites; gutters in sweeps.
- ✅ Screenshots → Task 14.
