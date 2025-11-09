# Idea Bank

This document collects future-facing feature and improvement concepts so we can quickly surface “what’s next” items on demand.

---

## Nutrition

- **Ingredient graph for nutrient lookup (new)**
  - **Goal:** Improve the Claude logging flow by mapping foods → ingredient lists → nutrient data.
  - **Why:** Direct nutrition data for composed dishes (e.g., tiramisu) is hard to find and leads to unbounded growth of single-use food entries.
  - **Approach:** Store canonical ingredient records (finite set), link foods to ingredients via recipes, and derive nutrient totals from the ingredient graph. This increases accuracy and keeps the database manageable.
