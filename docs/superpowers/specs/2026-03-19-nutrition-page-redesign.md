# Nutrition Page Redesign

## Goal

Redesign the nutrition page to surface the most important information first (today's macro progress), with progressive disclosure for secondary content. Improve visual design with accent-colored macro cards and clear hierarchy.

## Information Hierarchy

1. **Macro Hero** (always visible)
2. **Today's Meals** (collapsible, expanded by default)
3. **Vitamins & Minerals** (collapsible, collapsed by default)
4. **14-Day Averages** (collapsible, collapsed by default)
5. **Nutrient Goals** (collapsible, collapsed by default)
6. **Food Manager** (collapsible, collapsed by default)

## Data Mapping

### Nutrient identification

Calories are identified by `slug === 'calories'` in the `NutritionSummary.nutrients` array. The calories entry is extracted and rendered as the hero card; all other `group === 'macro'` nutrients render in the macro grid.

### Macro slug-to-color mapping

| Slug | Color | Palette source |
|------|-------|---------------|
| `calories` | `#7ED7C4` | pond 200 |
| `protein` | `#FFC075` | ember 200 |
| `carbohydrate` | `#BF6BAB` | bloom 300 |
| `fat` | `#C2D5FF` | sky 200 |
| `fiber` | `#82dcb8` | pond 300 |

Any macro nutrient not in this map gets a neutral fallback color (`theme.colors.textSecondary`).

### Remaining calculation

`remaining = goal - amount`. When `amount > goal`, display "over by X" in a warning color instead of "X remaining".

## Design

### 1. Macro Hero

**Calories card** — Full-width card with accent-tinted background and border (`rgba(accent, 0.08)` bg, `rgba(accent, 0.2)` border). Shows:
- "Calories" label (small uppercase)
- Current value large and bold in accent color (e.g. "1,820 kcal")
- Goal value ("of 2,350") and remaining ("530 remaining") right-aligned
- Gradient progress bar (8px tall)

**Macro grid** — 4-column grid below calories (responsive: 4 → 2 → 1 columns). Each card:
- Unique accent color per the slug-to-color mapping above
- Tinted background and border matching its accent
- Label, current/goal values, 4px progress bar, percentage

### 2. Today's Meals

Collapsible section with item count shown as a small pill badge (accent background, e.g. "5 items"). When expanded, shows each meal entry as a row with:
- Food name (left)
- Quantity + unit (right, muted)
- Edit/delete affordances (existing MenuPanel functionality)

### 3. Vitamins & Minerals

Collapsible section. Two-column layout inside:
- Left: Vitamins (name + % of goal + progress bar)
- Right: Minerals (name + % of goal + progress bar)
- Items exceeding 100% show the percentage in the nutrient's accent color with a filled dot (4px circle) to the left

### 4. 14-Day Averages

Collapsible section, collapsed by default. When expanded, shows macro nutrients only (no calories hero) in the same 4-column card grid layout, but with 14-day average values. Each card shows average amount, goal, and % of goal.

### 5. Nutrient Goals

Collapsible section, collapsed by default. Existing GoalsPanel component with editable goal values.

### 6. Food Manager

Collapsible section, collapsed by default. Existing FoodManager component (ingredients + recipes tabs).

## Edge States

### Loading
While `useNutritionDailySummary` is loading, show skeleton placeholder cards (pulsing `rgba(255,255,255,0.04)` blocks) matching the macro hero layout dimensions. This prevents layout shift.

### Empty
If `nutrients` array is empty (no data logged), show a single muted message: "No nutrition data logged today." in place of the macro hero.

### Error
If any hook returns an error, the section silently falls back to empty (existing codebase convention — no error banners).

### Null goals
If a nutrient's `goal` is null, hide the progress bar and "remaining" text; show only the amount.

## Collapse State

Persist open/closed state in `localStorage` key `'nutrition-sections'`. Default state: `{ meals: true, micro: false, averages: false, goals: false, foods: false }`.

The reader function merges stored values with defaults, ignoring unknown keys. This handles migration from the old `{ goals, foods }` shape gracefully — old keys are picked up where names match, new keys get defaults.

## Components

### Files to modify
- `src/pages/Nutrition.tsx` — Complete rewrite of page layout and structure

### Files to create
- `src/components/nutrition/MacroHero.tsx` — Calories hero card + macro grid
- `src/components/nutrition/MicronutrientPanel.tsx` — Vitamins & minerals two-column view

### Files to keep as-is
- `src/components/nutrition/MenuPanel.tsx` — Reuse existing meal list
- `src/components/nutrition/GoalsPanel.tsx` — Reuse existing goals editor
- `src/components/nutrition/FoodManager.tsx` — Reuse existing food manager
- `src/components/nutrition/NutritionDashboard.tsx` — No longer imported by Nutrition.tsx (replaced by MacroHero). Still imported by `DashboardNutritionSnapshot` — kept as-is.
- `src/components/nutrition/NutritionChatPanel.tsx` — Not part of the nutrition page (used via the global MonetChatBubble). Out of scope.

### Hooks used (no changes to any)
- `useNutritionDailySummary` — powers MacroHero and MicronutrientPanel
- `useNutritionHistory` — powers 14-Day Averages section
- `useNutritionMenu` — powers Today's Meals section (via MenuPanel)
- `useNutritionGoals` — powers Nutrient Goals section (via GoalsPanel)
- `useNutritionFoods` — used internally by FoodManager

## Responsive Behavior

- Macro grid: `repeat(4, 1fr)` → `repeat(2, 1fr)` at ≤ 768px → `1fr` at ≤ 480px
- Vitamins/Minerals grid: `1fr 1fr` → `1fr` at ≤ 600px
- Collapsible sections use `display: grid; grid-template-rows: 0fr/1fr` animation pattern (existing codebase convention)

## Styling

- Cards use theme tokens: `theme.colors.surfaceRaised`, `theme.colors.borderSubtle`, `theme.colors.overlay`
- Accent colors are hardcoded per-nutrient (not theme-dependent) since they represent fixed data categories
- Progress bar tracks use `theme.colors.overlay` (adapts to light/dark mode)
- Progress bar fill uses the nutrient's accent color; shifts to warning amber (`#F59E0B`) when exceeding 100%
- All typography uses existing `theme.fonts.heading` / `theme.fonts.body`
- Animation: `fadeUp` on page load (existing pattern)
- Collapsible sections: `grid-template-rows` transition with `prefers-reduced-motion` respect

## Accessibility

- Collapsible section headers are `<button>` elements with `aria-expanded`
- Progress bars have `role="progressbar"` with `aria-valuenow` (0-100), `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-label` naming the nutrient
- Macro cards use semantic markup (`<section>` with heading)
- Color is not the sole indicator — percentage text accompanies all progress bars

## Constraints

- Frontend-only changes — no backend/API modifications
- All existing hooks and data shapes remain unchanged
- Guest mode must continue to work with demo data
