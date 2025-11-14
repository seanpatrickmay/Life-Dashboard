# Hooks Folder

## Purpose
Stores reusable React hooks for data fetching and derived state used across pages and components.

## File Overview

| File | Description |
| --- | --- |
| `useInsight.ts` | Fetches the latest readiness insight (with polling). |
| `useMetricsOverview.ts` | Fetches metrics overview data for charts and summaries. |
| `useMetricSummary.ts` | Returns readiness metric deltas and scores. |
| `useNutritionFoods.ts` | CRUD helpers + cache for nutrition foods. |
| `useNutritionGoals.ts` | Loads nutrient defaults and user overrides, handles updates. |
| `useNutritionIntake.ts` | Provides daily summaries and 14-day averages. |
| `useClaudeChat.ts` | Manages Claude nutrition chat sessions and logged entries. |
| `useUserProfile.ts` | Fetches and updates the personalized user profile + scaling rules. |
