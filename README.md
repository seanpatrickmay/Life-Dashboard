# Life Dashboard

Production-ready hybrid stack that combines a Vercel-hosted Next.js frontend with Google Cloud Run services, Supabase Postgres/RLS, Stripe billing, and Vertex AI coaching insights.

---

## Quick Start (one command)

```bash
pnpm install && pnpm dev
```

That single command installs dependencies and boots the Next.js dev server. Optional background services (Cloud Run mocks) can be started with `pnpm dev:webhooks`, `pnpm dev:jobs`, and `pnpm dev:llm`.

---

## Environment Configuration

1. Copy the sample env file:
   ```bash
   cp .env.example .env.local
   ```
2. Provide the required secrets:
   - `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - Stripe keys (`STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, product & price IDs)
   - Garmin / Withings OAuth + webhook secrets
   - Google project, region, Vertex model, and optional `GOOGLE_APPLICATION_CREDENTIALS`
   - GCS bucket names for raw payload archiving
3. For local CLI access to Supabase and Google Cloud, export the same values in your shell or wrap them in a `.envrc`.

---

## Local Tooling & Database

| Task                         | Command                                                                 |
|------------------------------|-------------------------------------------------------------------------|
| Install deps & dev server    | `pnpm install && pnpm dev`                                              |
| Apply SQL schema             | `supabase db push --file supabase/sql/schema.sql --db-url "$DB_URL"`    |
| Apply RLS policies           | `supabase db push --file supabase/sql/rls_policies.sql --db-url "$DB_URL"` |
| Apply analytic views         | `supabase db push --file supabase/sql/views.sql --db-url "$DB_URL"`     |
| Seed synthetic data          | `pnpm tsx scripts/seed.ts`                                              |
| Run Vitest                   | `pnpm test`                                                             |
| Format & lint                | `pnpm format`, `pnpm lint`                                              |

> **Tip:** `scripts/seed.ts` will create an auth user (unless you provide `SEED_USER_ID`) and load 14 days of metrics, six activities, and mock insights—great for demos.

---

## Deploying the Frontend (Vercel)

1. Create a new Vercel project and import this repository.
2. Set environment variables in Vercel’s dashboard mirroring `.env.example`.
3. Configure build settings:
   - Framework: Next.js
   - Install command: `pnpm install`
   - Build command: `pnpm build`
4. Trigger a deployment; Vercel’s GitHub integration will use `.github/workflows/web.yml` for CI lint/build checks.

---

## Google Cloud Bootstrap

### CLI-only bootstrap

```bash
gcloud config set project $GCP_PROJECT_ID
gcloud services enable artifactregistry.googleapis.com run.googleapis.com secretmanager.googleapis.com \
  pubsub.googleapis.com cloudbuild.googleapis.com iamcredentials.googleapis.com
gcloud artifacts repositories create life-dashboard --location=$GCP_REGION --repository-format=docker
gcloud iam service-accounts create life-dashboard-ci --description="GitHub Actions deployer" --display-name="Life Dashboard CI"
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:life-dashboard-ci@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:life-dashboard-ci@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"
gcloud iam workload-identity-pools create github \
  --project=$GCP_PROJECT_ID --location="global" --display-name="GitHub Actions Pool"
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --workload-identity-pool="github" \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --allowed-audiences="https://googleapis.com/" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"
gcloud iam service-accounts add-iam-policy-binding life-dashboard-ci@$GCP_PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$GCP_PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$GITHUB_REPO"
```

Record the workload identity provider resource ID for GitHub Secrets (used by `.github/workflows/services.yml` and `migrations.yml`).

### Terraform (infra/gcp/terraform)

1. Update `infra/gcp/terraform/variables.tf` with your project/region.
2. Initialise:
   ```bash
   cd infra/gcp/terraform
   terraform init
   ```
3. Review & apply:
   ```bash
   terraform plan
   terraform apply
   ```
4. Terraform provisions the Artifact Registry, Workload Identity Pool, service accounts, and optional Pub/Sub topics/Scheduler jobs used by the Cloud Run services.

Deploy Cloud Run services by pushing to `main`; GitHub Actions will build and deploy via `.github/workflows/services.yml`.

---

## Supabase Management

1. **Create the project** in the Supabase UI and grab the project URL, anon key, and service role key.
2. **Apply schema** using the CLI (`supabase db push ...` as shown above) or via the GitHub Actions `migrations` workflow.
3. **Verify RLS**: run `supabase db diff` after changes; ensure policies in `supabase/sql/rls_policies.sql` remain intact.
4. **Seed data**:
   ```bash
   NEXT_PUBLIC_SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... pnpm tsx scripts/seed.ts
   ```

---

## Provider Integrations

### Garmin

1. Register an app in the Garmin Developer Portal; capture client ID/secret and webhook secret.
2. Expose local webhooks with ngrok or Cloudflared:
   ```bash
   ngrok http 8080
   ```
3. Update Garmin webhook URL to point at `https://<ngrok-id>.ngrok.app/garmin`.
4. For test payloads, use `scripts/mock_garmin_payload.json` with the Cloud Run `webhooks` service (e.g., `pnpm dev:webhooks` + `curl -X POST http://localhost:8080/garmin`).

### Withings

1. Create a Withings developer app and configure redirect/webhook URLs with your tunnel domain (e.g., `https://<ngrok-id>.ngrok.app/withings`).
2. Use `scripts/mock_withings_payload.json` to exercise the webhook endpoint locally.

> OAuth redirect helpers live under `services/webhooks/oauth`. In production, front these services with HTTPS (Cloud Run service URL or HTTPS Load Balancer).

---

## Stripe Test Mode

1. Create a product and two recurring prices (monthly/yearly) in Stripe Test mode.
2. Populate `.env.local` with `STRIPE_PRO_PRODUCT_ID`, `STRIPE_PRICE_PRO_MONTH_ID`, `STRIPE_PRICE_PRO_YEAR_ID`, plus public/secret keys.
3. Start the webhooks service locally (`pnpm dev:webhooks`) and expose with ngrok (Stripe requires HTTPS). Configure the Stripe webhook endpoint to `https://<ngrok-id>.ngrok.app/stripe`.
4. In the app:
   - Visit `/settings` and trigger “Upgrade”. The checkout session is created via `/api/stripe/create-checkout-session`.
   - Complete payment in the Stripe test checkout page (use cards like `4242 4242 4242 4242`).
5. Confirm that subscription events toggle the `feature_flags` table and that access to `/insights` becomes unlimited.

---

## Vertex AI Setup

1. Enable the Vertex AI API:
   ```bash
   gcloud services enable aiplatform.googleapis.com
   ```
2. Create a dedicated service account:
   ```bash
   gcloud iam service-accounts create vertex-runner --display-name="Vertex Runner"
   gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
     --member="serviceAccount:vertex-runner@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   ```
3. For Cloud Run: attach this service account to the `llm` service (`gcloud run services update ... --service-account vertex-runner@...`).
4. For local development: download a JSON key (store securely) and point `GOOGLE_APPLICATION_CREDENTIALS` to it.
5. Adjust `.env`:
   - `GCP_PROJECT_ID`, `GCP_LOCATION`
   - `VERTEX_MODEL` (e.g., `gemini-1.5-pro` or cost-saving `gemini-1.5-flash` for daily summaries)

---

## Cost Optimisation Tips

- **Cloud Run min instances**: set `--min-instances=0` for all services to scale to zero when idle.
- **Request concurrency**: configure sensible `--max-instances` and concurrency to avoid spikes (defaults are safe for small workloads).
- **Vertex AI models**: use `gemini-1.5-flash` for standard coaching loops; reserve `gemini-1.5-pro` for premium or complex analytics.
- **GCS storage classes**: raw payloads live in `GCS_BUCKET_RAW`; apply lifecycle rules to transition old data to Nearline/Coldline.
- **Scheduler frequency**: keep Cron jobs minimal (nightly recompute, 6-hour stale checks) to reduce invocation costs.
- **Supabase**: enforce RLS and prune stale `raw_events`/`activities` in the jobs service to keep table size manageable.

---

## Testing & QA

- **Vitest**: unit/spec tests live under `tests/`; run `pnpm test`.
- **ESLint/Prettier**: `pnpm lint`, `pnpm format`.
- **GitHub Actions**:
  - `web.yml`: lints/builds the Next.js app.
  - `services.yml`: builds/pushes Docker images and deploys Cloud Run services on `main`.
  - `migrations.yml`: applies Supabase SQL migrations.

---

## Additional Resources

- Architecture overview: `docs/architecture.txt`
- Postman collection: `collections/life-dashboard.postman_collection.json`
- Mock webhook payloads: `scripts/mock_garmin_payload.json`, `scripts/mock_withings_payload.json`
- Seed script: `scripts/seed.ts`

Happy building! Let us know if you extend providers, add new models, or wire in additional analytics—PRs welcome.
