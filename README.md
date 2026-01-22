# Life Dashboard

Life Dashboard is a self-hosted wellness hub that blends Garmin health data, nutrition tracking, and AI-generated insights into a calm, Monet-inspired experience. It is designed to feel like a living pond: soft layers, pixel textures, and lily pads that surface the metrics that matter most.

## Core Experiences

- **Dashboard**: Daily overview with Monet chat, a scrollable todo pad, and a nutrition snapshot.
- **Insights**: Single-metric focus view for HRV, resting HR, sleep hours, or training load with trend charts and daily scores.
- **Nutrition**: Guided nutrient explorer, daily goal progress, and 14-day averages driven by logged intake.
- **User Profile**: Demographics, unit preferences, Garmin connection status, and quick access to energy and macro targets.

## Highlights

- **Garmin ingestion**: HRV, resting HR, sleep, training load, activities, and energy data.
- **AI insights**: Vertex AI (Gemini) summaries with a Monet-style assistant and tool routing for nutrition and todos.
- **Nutrition system**: Ingredients, recipes, daily goals, and intake logging with AI-assisted parsing.
- **Rich UI**: Monet-inspired lily pads, pixel textures, and layered water motifs.
- **Docker-first**: One compose file spins up Postgres, FastAPI, and the Vite frontend.

## Architecture Overview

- **Frontend**: React + Vite + styled-components for the lily pad UI, charts, and animated scenes.
- **Backend**: FastAPI with async SQLAlchemy for ingestion, insights, and admin utilities.
- **Database**: PostgreSQL with time-series tables, activity storage, nutrition catalog, and AI insights.
- **AI services**:
  - Vertex AI (Gemini) for daily readiness narratives and Monet assistant reasoning.
  - Tool agents for nutrition parsing and todo generation backed by Vertex AI prompts.

## Tech Stack

- **Frontend**: React, Vite, styled-components, TanStack Query
- **Backend**: FastAPI, SQLAlchemy (async), Alembic, Loguru
- **Data**: PostgreSQL
- **AI**: Google Vertex AI (Gemini via google-genai)
- **Infra**: Docker, Docker Compose

## Repository Layout

```
backend/    FastAPI app, models, services, migrations
frontend/   React app, lily pad UI, charts, scenes
docs/       Setup, pipeline, operations, styling guides
scripts/    Manual ingest, debug tools, pixel asset generator
docker/     Docker compose stack definitions
```

## Getting Started (Docker)

1. Install Docker Desktop and confirm it is running.
2. Copy `.env.example` to `.env` and fill in the required values.
3. Start the stack:
   ```bash
   docker compose -f docker/docker-compose.yml up --build
   ```
4. Visit:
   - Frontend: `http://localhost:4173`
   - Backend: `http://localhost:8000`

You can also use the Makefile helpers:

```bash
make compose-up
make compose-down
```

## Configuration

All configuration lives in `.env`. The most important variables are grouped below.

### Database

| Variable | Purpose |
| --- | --- |
| `POSTGRES_HOST` / `POSTGRES_PORT` | Database host and port for container setup |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Core Postgres credentials |
| `DATABASE_URL` | Internal DB URL used by the backend container |
| `DATABASE_URL_HOST` | Local DB URL used by scripts and local tools |

### Auth and Sessions

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `local` or `prod` to control OAuth settings |
| `GOOGLE_CLIENT_ID_*` / `GOOGLE_CLIENT_SECRET_*` | Google OAuth credentials |
| `GOOGLE_REDIRECT_URI_*` | Google OAuth redirect URL |
| `ADMIN_EMAIL` | Admin user email (auto-elevated role) |
| `SESSION_COOKIE_*` | Cookie name, domain, secure, samesite settings |
| `SESSION_TTL_HOURS` / `SESSION_TTL_DAYS` | Session lifetime in hours/days |
| `CORS_ORIGINS` | Comma-delimited list of allowed frontend origins |

### Google Calendar

| Variable | Purpose |
| --- | --- |
| `GOOGLE_CALENDAR_REDIRECT_URI_*` | OAuth redirect URL for Calendar scopes |
| `GOOGLE_CALENDAR_WEBHOOK_URL` | Public URL to receive Calendar webhook notifications |
| `GOOGLE_CALENDAR_TOKEN_ENCRYPTION_KEY` | Symmetric key used to encrypt Calendar tokens |

### Garmin

| Variable | Purpose |
| --- | --- |
| `GARMIN_EMAIL` / `GARMIN_PASSWORD` | CLI fallback credentials for manual ingest |
| `GARMIN_TOKENS_DIR` | Container path where Garmin tokens are stored |
| `GARMIN_TOKENS_DIR_HOST` | Host path mounted into the container |
| `GARMIN_PASSWORD_ENCRYPTION_KEY` | Symmetric key used to encrypt Garmin credentials |
| `GARMIN_PAGE_SIZE` / `GARMIN_MAX_ACTIVITIES` | Pagination limits for ingestion |
| `READINESS_ADMIN_TOKEN` | Admin token for manual ingest endpoint |

### Vertex AI (Gemini)

| Variable | Purpose |
| --- | --- |
| `VERTEX_PROJECT_ID` | GCP project ID |
| `VERTEX_LOCATION` | Vertex region (ex: `us-central1`) |
| `VERTEX_MODEL_NAME` | Gemini model name |
| `VERTEX_SERVICE_ACCOUNT_JSON` | Container path to service account JSON |
| `VERTEX_SERVICE_ACCOUNT_JSON_HOST` | Host path mounted into the container |

### Frontend

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | API base URL for the frontend |

## Data and Insight Pipeline

1. **Garmin ingestion** pulls activities, HRV, resting HR, sleep, training load, and energy.
2. **Metric aggregation** normalizes daily values and computes rolling training load.
3. **Vertex AI** generates a daily readiness narrative stored in Postgres.
4. **Frontend** surfaces the latest insight plus 14-day trends and nutrition progress.

See `docs/pipeline.md` for the full flow.

## Operations

- **Manual ingest**: POST `/api/admin/ingest` with `X-Admin-Token` or run:
  ```bash
  make ingest
  ```
- **Scheduled ingest**: APScheduler runs daily to refresh metrics and insights.
- **Backups**: Snapshot the `pgdata` volume regularly.

## Scripts

Useful utilities live in `scripts/`:

- `manual_ingest.py` - trigger ingestion locally
- `debug_metrics.py` - inspect raw metric payloads
- `generate_pixel_assets.py` - rebuild Monet pixel sprites
- `sanity_db.py` - quick DB connectivity check

## Documentation

- `docs/setup.md` - local setup and Docker instructions
- `docs/pipeline.md` - data and insight pipeline details
- `docs/database.md` - schema notes
- `docs/operations.md` - maintenance and triggers
- `docs/frontend-styleguide.md` - UI and aesthetic guidelines

## Contributing

See `CONTRIBUTING.md` and `STYLE_GUIDE.md` for conventions, linting, and code style expectations.
