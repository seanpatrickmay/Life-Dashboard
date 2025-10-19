# Cloud Run Services

This directory contains TypeScript microservices designed for Google Cloud Run. Each service exposes an Express HTTP server with minimal business logic and clear TODOs for production hardening.

## Services

- `webhooks/`
  - Endpoints: `POST /garmin`, `POST /withings`, `POST /stripe`
  - Responsibilities: verify webhook signatures, drop raw payloads in GCS, fan out to Supabase, enqueue recompute jobs (TODO via Pub/Sub).
- `jobs/`
  - Endpoints: `POST /recompute?date=YYYY-MM-DD`, `POST /backfill?provider=garmin&days=90`
  - Responsibilities: nightly recompute of readiness/trends, provider backfills (TODO: implement API fetch + Pub/Sub orchestration).
- `llm/`
  - Endpoint: `POST /insights`
  - Responsibilities: call Vertex AI Gemini models, cache results by user/date/topics in Supabase.

## Local Development

```bash
# Webhooks service
npm run dev:webhooks

# Jobs service
npm run dev:jobs

# LLM service
npm run dev:llm
```

All services read shared utilities from `services/shared/` (Supabase client, GCS client, logger, schemas). Update `.env.local` (or use a secrets manager) with the variables listed in `.env.example` prior to running locally.

### Emulators & Tooling

- **Supabase/Postgres**: Use `supabase start` for a local stack or point `SUPABASE_DB_URL` to a local Postgres instance.
- **GCS**: For local testing, set `GCS_BUCKET_RAW` to a development bucket or run the [GCS emulator](https://github.com/fsouza/fake-gcs-server) and export `STORAGE_EMULATOR_HOST`.
- **Pub/Sub / Scheduler**: Use `gcloud beta emulators pubsub start` to emulate Cloud Scheduler triggers that publish to Pub/Sub topics.

## Production Build

```bash
# Build individual service bundles
npm run build:webhooks
npm run build:jobs
npm run build:llm

# Run compiled output (mirrors Cloud Run entrypoint)
npm run start:webhooks
```

See `Dockerfile.cloudrun` for a multi-service build template. Pass `--build-arg SERVICE=<webhooks|jobs|llm>` during `docker build` to target a specific service.
