# Smart Food Suggestions & Logging Accuracy

## Overview

An LLM-powered suggestion engine that recommends foods to quick-log based on recency and frequency of past intake. Paired with a comprehensive test harness validating end-to-end calorie accuracy from natural language input through to daily summary output.

## Goals

1. One-tap food logging from personalized suggestions
2. Suggestions ranked by recency and frequency, contextualized by time of day
3. Cached results, regenerated after each log event
4. End-to-end test coverage proving calorie accuracy through the full pipeline

## Non-Goals

- Nutrient gap analysis ("you're low on iron")
- Day-of-week pattern detection
- Meal grouping or meal-plan generation

---

## Data Model

### New table: `nutrition_suggestions`

| Column | Type | Purpose |
|--------|------|---------|
| `id` | serial PK | |
| `user_id` | int FK -> users, unique | |
| `suggestions` | jsonb | Array of suggestion objects |
| `stale` | boolean, default false | Set true after any intake log/update/delete |

The `Base` model provides `created_at` and `updated_at` automatically. `updated_at` serves as the "generated at" timestamp (the row is overwritten each time the agent runs).

### Suggestion object shape (jsonb array element)

```json
{
  "ingredient_id": 42,
  "recipe_id": null,
  "name": "Greek yogurt",
  "quantity": 1,
  "unit": "cup",
  "calories_estimate": 150,
  "reason": "logged 5 of last 7 days"
}
```

No new tables for history. Frequency and recency data is queried from the existing `nutrition_intake` table.

---

## Backend: Suggestion Agent

### Service: `NutritionSuggestionAgent`

Location: `backend/app/services/nutrition_suggestion_agent.py`

**Input (built from SQL queries on `nutrition_intake`):**
- Last 14 days of intake entries: food name, quantity, unit, timestamp, source
- Frequency counts: times each ingredient/recipe was logged in that window
- Current time of day (morning/afternoon/evening)
- Today's menu so far (to avoid re-suggesting already-logged items)

**Agent prompt strategy:**
Given the user's food logging history, suggest 8-10 foods they are likely to want to log right now. Prioritize foods logged frequently and recently. Consider time of day. For each suggestion, include the quantity and unit the user most commonly uses. Return JSON matching the suggestion object schema.

**Output:** Ranked suggestion array written to `nutrition_suggestions.suggestions`.

Uses the same OpenAI Responses API pattern as the existing `NutritionAssistantAgent`.

### Cache and staleness

1. `GET /api/nutrition/suggestions` checks `nutrition_suggestions` for the user
2. If no row exists, or `stale = true`, or `updated_at` is older than 6 hours: run the agent, write results, return
3. Otherwise return cached suggestions

After any intake is logged, updated, or deleted (manual, chat, or quick-log), a post-commit hook sets `stale = true` on the user's suggestion row.

### Quick-log endpoint

`POST /api/nutrition/quick-log` accepts:
```json
{
  "ingredient_id": 42,
  "recipe_id": null,
  "quantity": 1,
  "unit": "cup"
}
```

Delegates to the existing manual intake logging logic, then marks suggestions stale. The `day` parameter defaults to today (Eastern time), matching existing intake behavior.

**Recipe suggestions:** For recipes, `quantity` represents servings (e.g., `quantity: 1` = 1 serving). The `unit` field for recipe suggestions is always the recipe's `default_unit` (typically "serving"). The agent prompt explicitly instructs the LLM to use servings for recipes.

### API summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/nutrition/suggestions` | GET | Return cached suggestions or trigger agent |
| `/api/nutrition/quick-log` | POST | One-tap log + mark suggestions stale |

---

## Frontend: Quick Log UI

### New component: `QuickLogPanel`

Position: collapsible section on the Nutrition page between MacroHero and the Nutrition Assistant section.

**Layout:**
- Section header "Quick Log" with chip showing suggestion count
- Horizontal scrollable row of compact suggestion cards (pill-shaped)
- Each card displays: food name, quantity + unit, estimated calories
- Tap: immediately logs via `POST /api/nutrition/quick-log`, optimistic UI removes the card with a brief "Logged!" flash
- Edit icon on each card: expands inline quantity/unit editor before logging
- Loading state: skeleton pills while agent generates
- Empty state: "Log a few meals to get personalized suggestions"

### New hook: `useNutritionSuggestions`

- Queries `GET /api/nutrition/suggestions`
- On successful quick-log, invalidates suggestions query (triggers refetch since stale)
- Also invalidates menu and daily summary queries so the page updates

### Guest/demo mode

`fetchNutritionSuggestions` in `api.ts` returns a static array of ~6 hardcoded suggestions when `isGuestMode()` is true. No agent call in demo.

`quickLogFood` in guest mode optimistically removes the tapped suggestion from the local list (no persistence). This lets demo users experience the interaction without backend calls.

---

## Test Harness: Food Logging Accuracy

Location: `backend/tests/test_nutrition_accuracy.py`

### Layer 1: Nutrient math (unit tests)

- Seed ingredients with known calorie values (e.g., egg = 72 kcal/piece)
- Log intake via `POST /api/nutrition/intake/manual`
- Assert daily summary calories match expected totals
- Test cases:
  - Single ingredient, known quantity
  - Multiple ingredients summed
  - Recipe with components (calorie = sum of component calories / servings)
  - Fractional quantities (0.5 serving)
  - Unit conversions where applicable
- Primary assertion: calories. Secondary: protein, carbs, fat.

### Layer 2: AI extraction accuracy (integration tests)

- Send natural language to `POST /api/nutrition/assistant/message`
- Verify `logged_entries` response contains correct foods and quantities
- Test cases:
  - Simple: "I had 2 eggs" -> expect eggs, qty 2
  - Multi-food: "chicken salad and a banana" -> expect 2 entries
  - Quantities with units: "a cup of Greek yogurt" -> expect 1, cup
  - Ambiguous: "a bowl of oatmeal" -> verify reasonable quantity is assigned
  - Supplements: "took vitamin D and fish oil" -> expect 2 entries
- Marked `@pytest.mark.slow` (hits LLM API)

### Layer 3: End-to-end calorie pipeline (integration tests)

- Seed ingredients with exact known calorie values
- Send natural language -> verify daily summary calorie total
- Example: seed egg at 72 kcal/piece -> "I had 3 eggs" -> assert daily calories = 216
- Validates the full chain: extraction -> ingredient matching -> unit normalization -> intake logging -> summary aggregation
- Marked `@pytest.mark.slow`

### Test infrastructure

- Uses existing test database setup
- AI tests can be mocked for CI (record/replay) or run live with `@pytest.mark.slow`
- Calorie tolerance: exact match for deterministic paths, +/- 5% for AI extraction paths (to account for quantity interpretation variance)

---

## Files to create or modify

### New files
- `backend/app/services/nutrition_suggestion_agent.py` — Suggestion agent service
- `backend/app/db/models/nutrition_suggestions.py` — SQLAlchemy model (or added to existing nutrition models)
- `backend/tests/test_nutrition_accuracy.py` — Test harness
- `frontend/src/components/nutrition/QuickLogPanel.tsx` — Quick log UI
- `frontend/src/hooks/useNutritionSuggestions.ts` — Suggestions hook

### Modified files
- `backend/app/routers/nutrition.py` — Add `/suggestions` and `/quick-log` endpoints
- `backend/app/services/` — Import and wire suggestion agent
- `frontend/src/services/api.ts` — Add `fetchNutritionSuggestions`, `quickLogFood`, guest mode stubs
- `frontend/src/pages/Nutrition.tsx` — Add QuickLogPanel section
- `frontend/src/demo/guest/guestStore.ts` — Add guest suggestion data
- Alembic migration for `nutrition_suggestions` table
