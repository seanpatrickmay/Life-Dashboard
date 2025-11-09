# Layout Rules Spec (Scene‑Aware)

Goal: Keep the scene unobstructed while presenting data clearly using micro‑cards with no surfaces.

## Safe Zones (Apertures)

Compute geometry from CSS vars and image AR:

- Inputs
  - `--willow-offset` (px): inner edge margin on both sides
  - `--bridge-top` (px): top y of the arc image
  - `--bridge-ar` (unitless): arc image aspect ratio (w/h)
  - Viewport: `vw`, `vh` in px
  - Boat lanes: dynamic per direction

- Derived
  - arcWidth = vw − 2×willowOffset
  - arcHeight = arcWidth / bridgeAR
  - bridgeBand = Rect(x: willowOffset, y: bridgeTop, w: arcWidth, h: arcHeight)
  - reflectionTop = bridgeTop + arcHeight
  - reflectionHeight ≈ arcHeight × 0.55 (tune to asset)
  - reflectionBand = Rect(x: willowOffset, y: reflectionTop, w: arcWidth, h: reflectionHeight)
  - boatCorridorLow = band near bottom: yBottom ≈ 12vh; height ≈ 10vh
  - boatCorridorHigh = band near horizon: y ≈ ceil − 2vh; height ≈ 8vh

- No‑Fly Mask = union(bridgeBand, reflectionBand, activeBoatCorridor)

## Placement Heuristics

- Primary placement order
  1) Readiness hero micro‑cards (Score, Label/Scale, Intro) → top‑right stack, above bridgeBand, avoid center apex
  2) Metric stacks (HRV, RHR, Sleep, Load) → left rail as chips; insights on right; charts as thin sparklines beneath insights
  3) Secondary chips (delta summaries, day summary) → bottom‑left

- Staggering
  - Use CSS grid with row gaps 16–24px; vary column start to avoid continuous blocks
  - If item collides with No‑Fly Mask, shift to next available column/row

- Reflow algorithm (pseudo):
  - measure safeZones = viewport − No‑Fly Mask
  - for item in priorityList:
    - try preferred anchor rect; if intersects mask, try adjacent placements (left/right/down) with penalties
    - accept placement when intersection is empty; commit rect; continue

- Courtesy Fade
  - Detect overlapping flora/blossoms via element.getBoundingClientRect + hit test against known overlay sprites
  - On content hover/focus: reduce opacity of overlapping sprite by ~0.25; restore on leave

- Breakpoints
  - ≥1200px: 3‑column stagger grid, left rail chips; right side insights
  - 900–1199px: 2‑column grid; chips collapse tighter; hero micro‑cards stack vertically
  - ≤899px: Edge‑HUD mode — top/bottom HUD strip with horizontally scrollable chips; center left mostly free

## Spacing & Sizing

- Micro‑cards: 8–12px inner spacing; no surfaces; halos only
- Inter‑row gaps: 12–18px
- Charts: 12–16px height sparklines; 1.5–2px strokes; pattern fill only

## Implementation Notes

- PageBackground already computes `--bridge-top`; ensure `--willow-offset` is exposed and consistent with SceneComposer
- Add a lightweight LayoutEngine util:
  - API: `place(items: LayoutItem[], constraints: Constraints): Placement[]`
  - Data: preferred anchors, min size, avoidance masks
  - Output: top/left/col/row for inline styles or grid‑area values

- Use ResizeObserver to recompute on resize and on hero/bridge image load (when AR is known)

