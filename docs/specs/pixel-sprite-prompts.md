# Pixel Sprite Prompt Pack

One-shot prompts for additional assets. All should be PNG, transparent background, nearest-neighbor, no anti-aliasing, crisp pixels. Provide exact sizes and tiling where applicable.

## 1) Willow Tips (Longer, Thicker Strands)

- Filenames: `willow_tips_left_light.png`, `willow_tips_right_light.png`, `willow_tips_left_dark.png`, `willow_tips_right_dark.png`
- Size: 420×960 px each (portrait)
- Style: Monet-inspired pixel clusters; strand thickness 2–3 px with occasional 1 px flyaways; layered depth
- Colors (light): #4A8C6E, #7ED7C4, #B8F0DF, shadows #2E6F57
- Colors (dark): #20533E, #3F7D62, #7ED7C4, subtle cool #5E78C7 on tips
- Composition: asymmetrical drape, denser near top; bottom 20% fades to transparency

Prompt:
> Create a pixel-art PNG of willow tips (LEFT/RIGHT variant), 420×960, transparent background, crisp pixels. Monet-inspired, with 2–3 px strands, thicker and longer overall than existing. Light variant uses #4A8C6E, #7ED7C4, #B8F0DF with shadow #2E6F57; dark variant uses #20533E, #3F7D62, #7ED7C4 with subtle #5E78C7 highlights. No hard outlines; fade to transparent at bottom 20%.

## 2) Distant Lily Pads Ring (Background pads)

- Filenames: `pad_ring_distant_light.png`, `pad_ring_distant_dark.png`
- Size: 64×64 px
- Ring thickness: 1–2 px; center transparent
- Colors: light #7ED7C4/#B8F0DF, dark #5E78C7/#7ED7C4
- Usage: repeated sparse scatter at horizon distance

Prompt:
> Create a 64×64 pixel-art PNG of a distant lily pad ring (thin ring 1–2 px), transparent center and background, crisp pixels. Light: #7ED7C4/#B8F0DF; Dark: #5E78C7/#7ED7C4. No anti-aliasing.

## 3) Sparkle Speck Overlay (Sun Glint)

- Filenames: `sparkle_speck_light.png`, `sparkle_speck_dark.png`
- Size: 32×32 px (tileable as sparse overlay)
- Content: 3–5 one-pixel specks + 1 tiny 2×2 cross; high transparency
- Colors: light #FFBE8C/#FFE7CC; dark #C2D5FF/#E9F1FF

Prompt:
> Create a 32×32 pixel-art PNG tile with 3–5 single-pixel sparkles and one 2×2 cross sparkle, transparent background. Light palette #FFBE8C/#FFE7CC; dark palette #C2D5FF/#E9F1FF. Very subtle; no anti-aliasing.

## 4) Ripple Stripe (Shimmer Under Reflection)

- Filenames: `ripple_stripe_light.png`, `ripple_stripe_dark.png`
- Size: 120×22 px (repeat-x)
- Pattern: gently undulating horizontal wave bands, 1–2 px thickness, with dithering
- Colors: light #A5BEEB/#C9F3F6; dark #5E78C7/#294A90

Prompt:
> Create a 120×22 pixel-art PNG of a horizontal ripple stripe, transparent background, repeat-x friendly. Bands 1–2 px with subtle dithering. Light: #A5BEEB/#C9F3F6; Dark: #5E78C7/#294A90. Crisp pixels.

## 5) Cloud Reflection Tile (Moment-agnostic)

- Filenames: `cloud_reflect_soft.png`
- Size: 220×140 px (repeat)
- Style: soft clumped pixels, low-frequency pattern; works with soft-light/screen
- Colors: neutral bluish-lilac #B1A7FF/#C2D5FF with pale teal #B8F0DF flecks

Prompt:
> Create a 220×140 pixel-art PNG tile of soft cloud reflections on water, transparent background. Use #B1A7FF/#C2D5FF base with sparse flecks #B8F0DF. Low-frequency, not busy. Crisp pixels.

## 6) Koi Spark Trace (Optional)

- Filenames: `koi_trace_light.png`, `koi_trace_dark.png`
- Size: 96×42 px (non-tile; placeable)
- Content: dotted arc of 1–2 px points with 2–3 brighter specks; transparent
- Colors: light #FFC075/#FFBE8C; dark #E9F1FF/#C2D5FF

Prompt:
> Create a 96×42 pixel-art PNG of a short dotted arc (koi wake), 1–2 px dots with 2–3 brighter specks. Transparent background. Light: #FFC075/#FFBE8C; Dark: #E9F1FF/#C2D5FF. Crisp pixels.

## 7) Horizon Glow Band

- Filenames: `horizon_glow_light.png`, `horizon_glow_dark.png`
- Size: 512×128 px (repeat-x)
- Gradient: banded + dithered, fades to transparent top/bottom
- Colors: light #FFBE8C→transparent; dark #6F8BCB→transparent

Prompt:
> Create a 512×128 pixel-art PNG band for a horizon glow, transparent background, repeat-x. Banded+dithered fade toward transparent at top and bottom. Light: #FFBE8C; Dark: #6F8BCB.

## Placement & Naming

- Place under `frontend/src/assets/pixels/`
- Use as additions to existing registry; most are overlays with screen/soft-light blending

