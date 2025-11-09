# Theme & Motion Spec

## Moments & Palettes

Target moments and exact hex ramps. Morning/Noon emphasize light family; Twilight/Night emphasize dark family. Values below are the intended art direction; the implemented theme may be tuned to these.

- Morning (Sunrise — intense warm reds/peach/magenta)
  - waterDeep: #74306E
  - waterMid:  #FF7C61
  - waterLight:#FFD0AE
  - warmGlow:  #FF5E3F
  - bloomHighlight: #FFB2E2
  - Accent (UI): #FFC075, AccentSoft: rgba(255,192,117,0.28)

- Noon (Afternoon — intense light blue/teal)
  - waterDeep: #117A9E
  - waterMid:  #41C9D3
  - waterLight:#C9F3F6
  - warmGlow:  #FFBE8C
  - bloomHighlight: #B8F0DF
  - Accent (UI): #7ED7C4, AccentSoft: rgba(126,215,196,0.28)

- Twilight (Lilac/indigo, slightly lighter than night)
  - waterDeep: #24326A
  - waterMid:  #5E63B0
  - waterLight:#B1A7FF
  - warmGlow:  #FFA66E
  - bloomHighlight: #E7A2D4
  - Accent (UI): #BF6BAB, AccentSoft: rgba(191,107,171,0.28)

- Night (Cool navy/sky)
  - waterDeep: #0F1E45
  - waterMid:  #294A90
  - waterLight:#5E78C7
  - warmGlow:  #FFA66E
  - bloomHighlight: #E7A2D4
  - Accent (UI): #C2D5FF, AccentSoft: rgba(194,213,255,0.28)

## Text Halos (Tokens)

Use layered text-shadow stacks; no solid backgrounds.

- Heading halo (per moment)
  - Morning: 0 0 2px rgba(255,94,63,0.80), 0 0 8px rgba(255,124,97,0.45), 0 10px 24px rgba(116,48,110,0.20)
  - Noon:    0 0 2px rgba(65,201,211,0.80),  0 0 8px rgba(125,215,196,0.45), 0 10px 24px rgba(17,122,158,0.20)
  - Twilight:0 0 2px rgba(177,167,255,0.82), 0 0 8px rgba(191,107,171,0.45), 0 10px 24px rgba(36,50,106,0.22)
  - Night:   0 0 2px rgba(194,213,255,0.82), 0 0 8px rgba(94,120,199,0.45),  0 10px 24px rgba(15,30,69,0.24)

- Body halo (per moment) — slightly softer
  - Morning: 0 0 2px rgba(255,208,174,0.75), 0 0 6px rgba(255,124,97,0.30)
  - Noon:    0 0 2px rgba(201,243,246,0.75), 0 0 6px rgba(126,215,196,0.28)
  - Twilight:0 0 2px rgba(177,167,255,0.70), 0 0 6px rgba(94,99,176,0.28)
  - Night:   0 0 2px rgba(194,213,255,0.70), 0 0 6px rgba(41,74,144,0.28)

Implementation token proposal (Theme):
- theme.tokens.halo.heading[moment]
- theme.tokens.halo.body[moment]

## Layering (Z Indices)

- z:10 Sun/Moon glow if desired above flora; else tuck under willows
- z:6  Foreground flora (willow tips, select blossoms)
- z:5  HUD text/micro-cards (no surfaces)
- z:4  Bridge arc + reflection; Boat + reflection
- z≤0 Water, strokes, ripples, cloud reflections, vignette

Blend modes: prefer screen/overlay for glows and reflections; normal for text.

## Motion

- Sun/Moon orbit
  - Clockwise top half arc; 12:00 apex; 15:00 top-right; 18:00 right horizon
  - Behind bridge (z in midground); sun visible 05:00–19:00; moon visible 17:00–07:00

- Boat drift
  - Pass 1 (R→L): bottom track ~12vh, scale 1.0, 30s
  - Pass 2 (L→R): high track near horizon (ceiling−~2vh), scale 0.6, 30s
  - Loops alternate; facing direction flips with travel

- Boat bob/yaw
  - Hull: 33s loop, ±12px vertical, yaw ~±2.2°
  - Reflection: 30s loop, ±6px vertical, yaw ~±1.1°; sits ~8vh below hull track
  - Ripple shimmer under reflection: 12s linear flow; screen blend, low opacity

- Water motion
  - gentleDrift parallax on strokes/caustics: 16s–32s, alternating direction; opacity 0.2–0.35 total across layers

## Charts (Tokens)

- Series palette
  - HRV: stroke #7ED7C4; pattern: stipple
  - RHR: stroke #FFC075; pattern: crosshatch
  - Sleep: stroke #E6A9D3; pattern: stipple
  - Load: stroke #6F8BCB; pattern: zigzag

- Grid/ticks
  - grid: rgba(255,255,255,0.08) (day) / rgba(0,0,0,0.12) (night)
  - ticks: 50% of grid opacity; labels use body halo

- Tooltip
  - No box; floating label with body halo; micro-delta in accent color

## Nav & Accents

- Use theme.colors.accent for nav active underline and subtle borders
- Animate underline on hover with 200ms ease; no background fills

