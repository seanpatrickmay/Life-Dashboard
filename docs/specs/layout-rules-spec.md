# Layout Rules Spec (Scene‑Aware)

Goal: Keep the scene unobstructed while presenting data clearly using micro‑cards with no surfaces.

## Safe Zones (Apertures)

Compute geometry from CSS vars and image AR:

- Inputs
  - `--willow-offset` (px): scene side gutter (legacy willow variable)
  - `--bridge-top` (px): top y of the arc image
  - `--bridge-width` (px): rendered width of the bridge/reflection assets
  - `--bridge-left` (px): x origin of the bridge (right-justified)
  - `--bridge-ar` (unitless): arc image aspect ratio (w/h)
  - `--island-left-width`, `--island-right-width` (px): shoreline island spans
  - `--island-band-top` (px): y used to park the shoreline islands/text pads
  - Viewport: `vw`, `vh` in px
  - Boat lanes: dynamic per direction

- Derived
  - arcWidth = `--bridge-width` (fallback vw − 2×willowOffset if unset)
  - arcHeight = arcWidth / bridgeAR
  - bridgeBand = Rect(x: `--bridge-left`, y: bridgeTop, w: arcWidth, h: arcHeight)
  - reflectionTop = bridgeTop + arcHeight
  - reflectionHeight ≈ arcWidth / bridgeRefAR (tune to asset)
  - reflectionBand = Rect(x: `--bridge-left`, y: reflectionTop, w: arcWidth, h: reflectionHeight)
  - leftIslandRect = Rect(x: willowOffset, y: islandBandTop, w: `--island-left-width`, h: islandAssetHeight ≈ width × 0.35)
  - rightIslandRect = Rect(x: vw − willowOffset − `--island-right-width`, y: islandBandTop, w: `--island-right-width`, h: islandAssetHeight ≈ width × 0.28)
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

- PageBackground already computes the scene vars; ensure `--willow-offset`, `--bridge-width`, `--bridge-left`, and shoreline island widths stay in sync with SceneComposer
- Add a lightweight LayoutEngine util:
  - API: `place(items: LayoutItem[], constraints: Constraints): Placement[]`
  - Data: preferred anchors, min size, avoidance masks
  - Output: top/left/col/row for inline styles or grid‑area values

- Use ResizeObserver to recompute on resize and on hero/bridge image load (when AR is known)
