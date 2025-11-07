Monet Pixel Assets (PNG)

This folder contains hand‑generated pixel PNGs produced by `scripts/generate_pixel_assets.py` (pure Python, no external deps). They are small tiles/sprites intended for CSS layering and component decoration.

Files (PNG RGBA, nearest-neighbor safe)
- lily_light_{1..4}.png / lily_dark_{1..4}.png — 24×24 pads with subtle notch and shading
- blossom_light_{1..4}.png / blossom_dark_{1..4}.png — 16×16 single blossoms
- blossom_cluster_light_{1..3}.png / blossom_cluster_dark_{1..2}.png — 48×48 grouped blossoms (anchor overlays)
- water_base_light.png / water_base_dark.png — 16×16 seamless water tiles
- water_reflection_light.png / water_reflection_dark.png — 32×16 shimmer overlays (transparent, tile X)
- cloud_reflect_light.png / cloud_reflect_dark.png — 32×16 cloud highlight tiles (transparent)
- ripple_light.png / ripple_dark.png — 16×16 ripple-line tiles (transparent)
- reeds_light.png / reeds_dark.png — 24×24 seamless reed band tiles
- willow_frond_light.png / willow_frond_dark.png — 48×96 no-repeat edge overlays
- microgrid_light.png / microgrid_dark.png — 8×8 canvas grain
- dither_light.png / dither_dark.png — 8×8 chart fill dithers
- speckles_dark.png — 12×12 starry speckles tile
- frame_corners_light.png / frame_corners_dark.png — 12×12 gilded corner motifs
- stroke_stipple.png / stroke_crosshatch.png / stroke_zigzag.png — 8×8 chart stroke tiles
- vignette_radial_light.png / vignette_radial_dark.png — 256×256 radial overlays
- bridge_arc_light.png / bridge_arc_dark.png — 220×80 Japanese bridge silhouettes (no-repeat)
- bridge_arc_reflection_light.png / bridge_arc_reflection_dark.png — 220×60 shimmering reflections
- koi_silhouette.png — 24×12 koi top view
- boat_silhouette.png — 48×16 scull silhouette
- README.md (this file)
- _previews/ — 3×3 tiled preview mosaics for seamless assets

Usage Plan (not yet wired)
- PageBackground (light):
  - layers: `water_base_light` → `water_reflection_light` → `lily_light_*` (sparse) → anchored `blossom_light_*`/`blossom_cluster_*` → `reeds_light` bottom band → `microgrid_light`
  - motion: parallax drift on `ripple_light`
- PageBackground (dark/twilight/night):
  - layers: `water_base_dark` → `water_reflection_dark` / `cloud_reflect_dark` → `lily_dark_*` → anchored `blossom_dark_*` (few) → `speckles_dark` (twilight/night) → `reeds_dark` where needed → `microgrid_dark`
  - edge vignettes: `willow_frond_dark` for twilight/night; `vignette_radial_dark` for global falloff
- Cards/Nav: use `frame_corners_*` plus `microgrid_*` as background.
- Charts:
  - use `dither_*` and `stroke_*` tiles as `<pattern>` fills for HRV/RHR/Sleep/Load series.
- ReadinessCard: place a blossom or lily badge sprite in corner.
- Feature overlays: `bridge_arc_*` + reflections, `koi_silhouette`, `boat_silhouette`, `willow_frond_*` used sparingly per time-of-day.

Regenerating
```
python3 scripts/generate_pixel_assets.py
```
