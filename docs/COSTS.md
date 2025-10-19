# Cost & Budgeting Guide

Life Dashboard is designed to scale to zero and stay lightweight, but production workloads still incur charges. Use this guide to keep monthly spend predictable.

## Core Components & Tuning

| Service           | Notes | Cost Tips |
|-------------------|-------|-----------|
| **Cloud Run** (webhooks, jobs, llm) | Containers scale to zero once idle. | Set `--min-instances=0`, tune `--max-instances` to expected concurrency, and use CPU throttling (`--cpu-throttling`). |
| **Artifact Registry** | Holds Docker images. | Enable automatic image cleanup to remove unused tags older than 14 days. |
| **Supabase** | Managed Postgres + Auth + Storage. | Prune raw payloads (via jobs service), and limit historical retention for activities/raw events. |
| **Vertex AI** (Gemini) | Generates insights. | Default to `gemini-1.5-flash` for daily automations and reserve `gemini-1.5-pro` for premium runs. Cache responses (already implemented) to avoid duplicate calls. |
| **GCS** | Stores webhook payloads. | Set lifecycle rules to move objects to Nearline/Coldline or delete after 30+ days. |
| **Stripe** | Billing platform. | Test mode is free. Production charges are per-transaction; no extra tuning required. |

## Enable Budget Alerts (GCP)

1. **Create a budget**:
   ```bash
   gcloud beta billing budgets create \
     --billing-account=$BILLING_ACCOUNT \
     --display-name="Life Dashboard Budget" \
     --budget-amount=200 \
     --threshold-rule=percent=0.5 \
     --threshold-rule=percent=0.8 \
     --threshold-rule=percent=1.0 \
     --all-updates-rule-pubsub-topic=projects/$GCP_PROJECT_ID/topics/billing-alerts
   ```
2. **Create the Pub/Sub topic** (if not already):
   ```bash
   gcloud pubsub topics create billing-alerts
   ```
3. **Subscribe notifications** (Cloud Function, email webhook, or Slack integration via Cloud Run). For quick email notifications, use Cloud Monitoring alerting policies.
4. **Tighten budgets per environment**: Prod vs staging can have separate budgets to spot runaway builds or QA costs independently.

## CI/CD Optimisation

- GitHub Actions build Docker images only on `main` pushes (`services.yml`). Avoid pushing large test tags.
- Use `pnpm` caching in CI (already configured) to minimise cold-start minutes.
- Cache Terraform plugins/state using remote backends (e.g., GCS bucket) to reduce `terraform plan` time.

## Vertex AI Cost Controls

- Set `LLM_RATE_LIMIT_PER_MINUTE` & `NEXT_PUBLIC_FREE_INSIGHTS_LIMIT` to match quota tiers.
- For nightly jobs, call the LLM service in batches and reuse cached insights via `services/shared/cache`.
- Monitor Vertex usage in the GCP console; create a custom alert for `Prediction requests` spikes.

## Supabase Usage Tracking

- Track `usage_records` to understand per-user feature costs. Use the jobs service to rollup monthly usage and disable premium features for heavy abuse.
- Automatic Postgres backups are handled by Supabase; schedule vacuum/analyze via Supabase cron to keep query plans efficient.

## Miscellaneous Tips

- **Logging**: Route structured logs to Cloud Logging with exclusion filters to avoid high storage volumes (e.g., exclude health checks).
- **Testing environments**: Restrict staging to manual start (Cloud Run `--min-instances=0`) and disable Cron triggers unless testing scheduled jobs.
- **Data retention**: Implement a scheduled job to archive or delete `raw_events` older than N days to keep Supabase lean.

Review costs monthly and adjust budgets, rate limits, and lifecycle policies as traffic grows.
