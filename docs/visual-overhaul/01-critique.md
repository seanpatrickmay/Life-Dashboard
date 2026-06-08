# Visual Overhaul — Critique (current site vs the Refined-Retro goal)

> Design-director critique (impeccable:critique framework), grounded in the guest-mode screenshots (Today/Read/Reflect/Body, desktop + mobile), `monetTheme.ts`, `Card.tsx`, and the E0 audit. Judged against the ratified **Refined-retro** direction (`.impeccable.md`).

## Anti-Patterns Verdict — PARTIAL FAIL (the backdrop saves it)
The custom pixel-art pond is genuinely distinctive — but the **UI layer** carries classic AI-slop tells:
- **Translucent "glass" surfaces** — cards/overlays at `rgba(...,0.04–0.92)` over a busy backdrop (glassmorphism-adjacent; muddy, low-contrast).
- **Soft blurry drop shadows** + **smooth 22px rounded corners** = the "rounded rectangle with generic drop shadow" tell.
- **No committed system** — the UI reads as a generic translucent dashboard *dropped onto* a beautiful painting, rather than one crafted artifact.
**Verdict:** background passes (distinctive); the chrome would read as "an AI made this UI." That gap is the whole job.

## Overall impression
A beautiful, soulful pixel-art pond **undermined by a modern, translucent, soft-shadowed UI** that doesn't speak its language. **Biggest opportunity:** harden the UI into the pixel/neo-brutalist system so the entire screen reads as ONE intentional, crafted thing.

## What's working (keep)
1. **The pond scene** — lush, custom, moment-based, atmospheric. The identity. (Keep lush.)
2. **VT323 headings** — real pixel character where used.
3. **Hue families** (sky/bloom/pond/ember/lilac/neutral) — pleasant, cohesive bones to build the principled palette on.

## Priority issues (ordered)
1. **Translucent surfaces muddy everything + kill hierarchy.** *Why:* `surfaceRaised` 4% / `overlay` 6% / `backgroundCard` 92% over the busy pond → weak contrast, no clear 60-30-10, cards barely read as surfaces. *Fix:* **solid, opaque principled fills** in 60-30-10 tiers, WCAG-AA both modes. *Command:* `/colorize`.
2. **Soft shadow + 22px radius = modern AI-card on a pixel backdrop.** *Why:* the chrome clashes with the pixel language; reads templated. *Fix:* **hard offset (pixel) shadow** (`shadows.pixel`, already defined) + **thick 2–3px borders** + **squarer corners** (+ optional `frame_corners` sprites). *Command:* `/bolder` (+ `/normalize`).
3. **No pixel UI SYSTEM.** *Why:* Card/Button/Input/Nav/Chip are each ad-hoc; the style won't scale or cohere. *Fix:* build shared **pixel primitives** so every surface speaks one language. *Command:* `/extract` + `/normalize`.
4. **Accent isn't scarce.** *Why:* pond-teal applied flatly everywhere → no "10% accent" punch for CTAs/active. *Fix:* reserve a **scarce accent** (CTAs/active/focus) per 60-30-10; everything else neutral/secondary. *Command:* `/colorize`.
5. **Type hierarchy underused.** *Why:* VT323 appears in spots but the heading/body scale is flat in places; pixel character is inconsistent. *Fix:* commit **VT323 to headings/chrome** + a clear modular scale; keep Space Grotesk body legible. *Command:* `/typeset`.

## Minor observations
- `image-rendering: pixelated` already on `Card` (good foundation).
- `frame_corners_{light,dark}` + `shadows.pixel` are **defined but unused** — free wins for the pixel-card treatment.
- Halo text-shadows look nice over the painting but can **reduce contrast on solid cards** — re-tune (or drop) on opaque surfaces.
- Charts use soft fills — could adopt **dithered/pixel fills** (the `stroke` + `dither` sprites exist) for cohesion.

## Questions to consider
- What if **active/hover cards** cast their hard pixel shadow in the **accent colour** (cheap, characterful state feedback)?
- What does a **fully-committed pixel Button** look like (solid fill, thick border, hard shadow that "presses" on click)?
- Should the **nav** become a pixel "shelf/tab" set rather than soft underlines?
- Where does the pond **peek through** intentionally (between cards) so the backdrop stays the soul without competing?
