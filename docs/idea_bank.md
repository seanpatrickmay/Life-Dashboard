# Idea Bank

This document collects future-facing feature and improvement concepts so we can quickly surface “what’s next” items on demand.

---

## Nutrition

- **Ingredient graph for nutrient lookup (new)**
  - **Goal:** Improve the Claude logging flow by mapping foods → ingredient lists → nutrient data.
  - **Why:** Direct nutrition data for composed dishes (e.g., tiramisu) is hard to find and leads to unbounded growth of single-use food entries.
  - **Approach:** Store canonical ingredient records (finite set), link foods to ingredients via recipes, and derive nutrient totals from the ingredient graph. This increases accuracy and keeps the database manageable.

- **Composable foods and units (new)**
  - **Goal:** Let each food be defined either as a base item with intrinsic nutrient data or as a combination of other foods with quantity units (grams, servings, cups, etc.).
  - **Why:** Users often log staples like "Breakfast sandwich" or "Protein bowl" that are reusable mixes of known items; recomputing their macros manually is error-prone and bloats the food catalog with near-duplicates.
  - **Approach:** Extend the food schema with a `type` discriminator (single vs. composed) and recipe units table that references other foods plus per-unit weights. During logging we resolve the recipe tree, aggregate nutrients, and allow editing by swapping or scaling component foods.

- **Lily pad leafs for displaying stats**

- **Menu give some quick select options, and suggested foods based on missing nutrients**

- **Manual modalities for data entry**

---

## Scene UI Enhancements

- **Blossom adornments on “excellent” states (new)**
  - Goal: Celebrate outstanding metric states (e.g., HRV well above target, sleep hitting goal) with subtle blossom overlays or halos on the corresponding lily pads.
  - Notes: Visual-only; no additional interactions required. Respect color-blind safety by pairing adornments with small iconography or badges.

- **Static interaction suggestions (new)**
  - Goal: Provide clear but non-interactive affordances until we wire live behavior.
  - Suggestions:
    - “Tap to view details” label etched lightly on pad footer.
    - Micro sparkline placeholder beneath value (no hover needed).
    - “Hold for actions” ghost text (non-functional for now).
    - Disabled state copy: “Unavailable — data missing” directly on the pad.

## Read/Research

- **Curated reading list (future)**
  - Goal: After we gain a holistic view of the user (training, recovery, nutrition, mindset, creative pursuits), surface long-form articles across *all* facets of their life—art, philosophy, training science, nutrition, mindfulness—so the experience feels tailored to the whole person, not just their metrics.
  - Approach (later stage): Maintain a vetted library with metadata (pillar tags, tone, depth). Once personalization is mature, recommend 3–5 rotating pieces in-app with Monet-themed blurbs and contextual relevance (e.g., creativity essays when the user has an off day, nutrition science when macro balance dips).
  - Notes: Defer implementation until the system can ingest enough user signals to make meaningful cross-domain suggestions; otherwise the list should remain dormant.
