# Pixels Folder

## Purpose
Holds the procedurally generated Monet sprite sheet used by the scene composer (lilies, blossoms, water, reflections, reeds, willow strands, feature overlays, stroke tiles, etc.). All files are PNGs emitted by `scripts/generate_pixel_assets.py`.

## File Overview

| Asset(s) | Description / Usage |
| --- | --- |
| `lily_{light,dark}_{1-4}.png` | Tiled lily-pad sprites for base coverage. |
| `pad_small_{mode}_{1-3}.png`, `pad_ring_{mode}.png` | Sparse lily pads scattered via the scene composer. |
| `blossom_{mode}_{1-4}.png`, `blossom_small_{mode}_{1-3}.png`, `blossom_cluster_*`, `blossom_glow_{mode}.png` | Blossom sprites and glow underlays used on cards/scene overlays. |
| `water_base_{mode}.png`, `water_reflection_{mode}.png`, `cloud_reflect_{mode}.png`, `water_stroke_{size}_{mode}.png` | Layered water textures and reflections. |
| `ripple_{mode}.png`, `caustic_ripple_fine_{mode}.png` | Ripple tiles for parallax overlays. |
| `reeds_{mode}.png`, `reeds_edge_{mode}.png`, `willow_frond_{mode}.png`, `willow_strands_{side}_{mode}.png` | Vegetation sprites (edge reeds and hanging willows). |
| `bridge_arc_{mode}.png`, `bridge_arc_reflection_{mode}.png`, `koi_silhouette.png`, `boat_silhouette.png` | Feature-scene overlays (bridge, koi, boat). |
| `microgrid_{mode}.png`, `dither_{mode}.png`, `speckles_{mode}.png`, `vignette_radial_{mode}.png`, `vignette_haze_{mode}.png` | Utility textures for cards and night speckles. |
| `stroke_{stipple,crosshatch,zigzag}.png` | Fill patterns applied to charts. |
| `_previews/` | Auto-generated 3x3 previews of tileable assets. |
