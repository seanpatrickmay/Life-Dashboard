# Hooks Folder

## Purpose
Stores reusable React hooks for data fetching and derived state used across pages and components.

## File Overview

| File | Description |
| --- | --- |
| `useInsight.ts` | Fetches the latest readiness insight (with polling). |
| `useMonetChat.ts` | Handles Monet chat state, calling the assistant endpoint and invalidating related caches. |
| `useMetricsOverview.ts` | Fetches metrics overview data for charts and summaries. |
| `useMetricSummary.ts` | Returns readiness metric deltas and scores. |
| `useNutritionFoods.ts` | CRUD helpers + cache for nutrition foods. |
| `useNutritionRecipes.ts` | CRUD helpers + cache for recipes and components. |
| `useNutritionGoals.ts` | Loads nutrient defaults and user overrides, handles updates. |
| `useNutritionIntake.ts` | Provides daily summaries and 14-day averages. |
| `useClaudeChat.ts` | Manages Claude nutrition chat sessions and logged entries. |
| `useJournal.ts` | Fetches journal day/week data and submits new journal entries. |
| `useTodos.ts` | Fetches and mutates per-user to-do items. |
| `useTodoClaudeChat.ts` | Manages Monet chatbot sessions for creating to-do items. |
| `useUserProfile.ts` | Fetches and updates the personalized user profile + scaling rules. |
| `useVisitRefresh.ts` | Triggers background refreshes on visits and invalidates caches after completion. |
