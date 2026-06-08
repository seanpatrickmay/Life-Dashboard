# Visual Overhaul — Research (skills + principles)

> Goal (Sean): make the site more artistically beautiful — **principled solid-colour themes, stylistic cards, full commitment to the pixel-art identity.** Workflow: research → critique → brainstorm → improvement plan → implementation plan → implement → PR.

## Design-skill toolkit (the "research skills" answer)
- **`impeccable:critique`** — evaluate design effectiveness (the critique step). **`impeccable:audit`** — a11y/contrast/theming/responsive quality.
- **`superpowers:brainstorming`** — lock artistic direction with Sean (mandatory before creative work).
- **`superpowers:writing-plans`** — improvement → implementation plan. **`superpowers:subagent-driven-development`** — execute.
- Implementation design skills: **`frontend-design`** (distinctive, anti-generic), **`impeccable:colorize`** (principled colour), **`impeccable:typeset`** (type), **`impeccable:arrange`** (rhythm), **`impeccable:bolder`** (commit to pixel-art), **`impeccable:animate`/`delight`** (charm), **`impeccable:polish`** (final pass).
- **`finishing-a-development-branch`** + the repo PR-screenshots rule for the PR.

## Principle 1 — pixel-art UI done well
- `image-rendering: pixelated` keeps sprites/borders crisp; align to integer / 8px grid, integer sizes ×8. (Card already sets `image-rendering: pixelated`.)
- Embed pixel fonts (VT323 is embedded) — but pixel fonts are hard to read small → **headings/chrome only; body stays legible** (Space Grotesk). Generous letter/line spacing.
- **Accessibility is harder with pixel art:** low-res type/icons struggle with WCAG contrast; decorative sprites need `aria-hidden`/alt. Keep body contrast AA.
- **Make it a modular SYSTEM** (pixel Card/Button/Input/Nav/Chip primitives) so the style scales site-wide instead of being a one-off gimmick. ← the key lever.

## Principle 2 — principled colour ("solid colour, good decisions")
- **60-30-10:** 60% dominant surface, 30% secondary, **10% scarce accent** (CTAs/active) — contrast through scarcity. Today the accent (pond-teal) is the only accent + everything is translucent → no clear hierarchy.
- **3-layer tokens:** primitive (hues) → semantic (`text-primary`, `action-primary`, `surface`, `surface-raised`) → component. Name by function, not hue.
- Derive ~50–80 values from **5–7 base hues** (palette already has sky/bloom/pond/ember/lilac/neutral — good bones).
- **WCAG AA** every text/bg + UI pair (4.5:1 text, 3:1 large/UI); validate **light AND dark**.

## Principle 3 — stylistic cards = pixel / neo-brutalist
- **Hard offset shadow:** `box-shadow: Npx Npx 0 0 <solid>` (0 blur/spread). The theme's `shadows.pixel` (`6px 6px 0 rgba(23,20,33,0.2)`) is exactly this — **defined but unused** (Card uses `shadows.soft`).
- **Thick borders** (2–4px solid) vs the current 1px soft border; **solid fills** (reject transparency/gradients); **squarer corners** vs the current 22px radius. Bold accent.

## Current-state notes (grounding)
- The **background IS lush pixel-art** (full Monet pond: lilies/water/clouds/willows/koi/bridge sprites, moment-based palettes) — already strong.
- The **cards/UI chrome are MODERN** — smooth 22px radius, soft blurry `shadows.soft`, **translucent fills** (`surfaceRaised` 4% / `overlay` 6% / `backgroundCard` 92%). **Mismatch** with the pixel background = the core problem + Sean's three asks.
- `shadows.pixel` + `frame_corners_{light,dark}` sprites are **defined but underused**. `image-rendering: pixelated` already on `Card`.
- Fonts: VT323 (heading/pixel) + Space Grotesk (body). Palette: sky/bloom/pond/ember/lilac/neutral.

## Emerging direction (to confirm in brainstorm)
A **pixel / neo-brutalist-leaning component system** layered over the existing pixel pond: **solid colour** surfaces (kill translucency) on a principled 60-30-10 + semantic-token palette (WCAG AA, both modes); **stylistic cards** = thick pixel border + hard offset shadow (`shadows.pixel`) + solid fill + squarer corners + optional `frame_corners`; **full pixel-art** = VT323 chrome, pixel buttons/inputs/nav/chips as a system. **Keep body text legible.** Open questions for Sean: how far (refined-retro ↔ full 8-bit), palette direction, whether to retain the watercolor scene or harden it.

## Sources
- Pixel-art on the web: [kirupa — preserving pixel art](https://www.kirupa.com/hodgepodge/preserving_pixel_art_aesthetics.htm) · [sage.agency — when pixel art belongs](https://sage.agency/blog/websites-that-use-cool-pixel-art-design/) · [Smashing — rethinking pixel-perfect](https://www.smashingmagazine.com/2026/01/rethinking-pixel-perfect-web-design/) · [618media — pixel typography](https://618media.com/en/blog/how-to-pixel-typography-in-web-design/)
- Colour systems: [60-30-10 guide](https://www.sixtythirtyten.co/blog/60-30-10-rule-complete-guide) · [scalable accessible colour system (UX Collective)](https://uxdesign.cc/designing-a-scalable-and-accessible-color-system-for-your-design-system-f98207eda166) · [UXPin — colour consistency / tokens](https://www.uxpin.com/studio/blog/color-consistency-design-systems/) · [WCAG contrast guide](https://dev.to/_d7eb1c1703182e3ce1782/wcag-color-contrast-guide-accessible-web-design-4kcn)
- Pixel/neo-brutalist cards: [neobrutalism.dev — card](https://www.neobrutalism.dev/components/card) · [neubrutalism — definitive guide](https://neubrutalism.com/) · [hard-shadow / brutalist UI](https://madegooddesigns.com/neobrutalism-web-design/)
