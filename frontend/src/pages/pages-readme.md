# Pages Folder

## Purpose
Route-level components that compose domain-specific UI for the Life Dashboard.

## File Overview

| File | Route | Description |
| --- | --- | --- |
| `Today.tsx` | `/` | Hero morning brief, greeting strip, summary chips, quick-capture, and supporting grid. Formerly `Dashboard.tsx`. |
| `Read.tsx` | `/read` | News feed with category filter strip, AI dev section, and tune drawer. Formerly `News.tsx`. |
| `Reflect.tsx` | `/reflect` | Book-style journal with saved-reads nudge. Formerly `Journal.tsx`. |
| `Body.tsx` | `/body` | Sticky-tab hub: Health (readiness + insight history) and Nutrition (macros, meals, goals). Merges former `Insights.tsx` + `Nutrition.tsx`. |
| `Calendar.tsx` | `/calendar` | Rolling week calendar view with events, todos, and detail drawer. |
| `Projects.tsx` | `/projects` | Project-centered todo management with suggestions and assignment workflows. |
| `FoodManagerPage.tsx` | `/settings/food-db` | Food database browser (search, add, edit entries). |
| `Login.tsx` | `/login` | Authentication page. |
