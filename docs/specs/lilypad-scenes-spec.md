# Lily Pad Scenes Spec

Authoritative mapping of lily pads “beneath the bridge” for each scene. Pads are large, fixed-size, and staggered left/right downward unless noted. Use the time-based pad sprites placed in `frontend/src/assets/pixels/`:

- Day (used for Morning and Noon): `lily_pad_text_day.png`
- Twilight: `lily_pad_text_twilight.png`
- Night: `lily_pad_text_night.png`

Slight visual scaling (discrete steps) is allowed; placement/hitboxes remain fixed.

---

## Dashboard

- Metrics (fixed-size pads)
  - Sleep — rendered atop time-based pad sprite for current moment
  - HRV — rendered atop time-based pad sprite for current moment
  - RHR — rendered atop time-based pad sprite for current moment

- Arrangement
  - Staggered left/right down the page under the bridge band.

- States
  - Normal: title + value text on the pad.
  - Error/missing: show an inline error label on the pad body: “Unavailable — data missing”.

- Notes
  - No dynamic sizing. Future enhancement: blossom adornments on excellent states (see Idea Bank).

---

## Insights

- Categories
  - HRV, RHR, Sleep, Training Load.

- Count and grouping
  - 8 pads total: for each category, one “Title+Value” pad and one “Graph” pad, both using the time-based pad sprite for the current moment.

- Arrangement
  - Staggered left/right downward.

- Interactions
  - None for now; static display only.

---

## Nutrition

- Pads
  - Today’s Menu — rendered atop time-based pad sprite for current moment
  - Today’s Stats (cycle macros/vitamins/minerals) — rendered atop time-based pad sprite for current moment
  - Palette — rendered atop time-based pad sprite for current moment
  - 14‑day Avg Goal % Hit — rendered atop time-based pad sprite for current moment

- Behavior
  - Stats pad cycles between macros → vitamins → minerals (static hint text until hooked up).

- Arrangement
  - Staggered left/right downward.

---

## Settings

- Split into two sections; no page-level “Settings” header.
  - Time Test controls
  - Monet Pixel Art controls

- Pads
  - Settings do not use lily pads; these remain standard UI controls.

---

## Global

- Visual language
  - Large lily pads only; fixed size; staggered layout beneath bridge band.

- Error handling
  - If a pad’s data is missing, render an on-pad message: “Unavailable — data missing”.

- Accessibility note (minimal for now)
  - Ensure the pad text (title/value/error) is always present so information is not color-only.
