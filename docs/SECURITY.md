# Security Guide

Life Dashboard handles health telemetry, billing, and personally identifiable information. Use the checklist below to keep deployments hardened.

## Secrets & Identity

- **Environment variables**: inject through Vercel/Cloud Run secret managers. Never commit `.env.local`. Rotate keys quarterly.
- **Supabase service role**: restrict usage to server-side scripts (Cloud Run, GitHub Actions). App Router routes should use the anon key—never leak the service role to the browser.
- **Google Cloud IAM**: each Cloud Run service uses the minimum IAM role it needs (`vertex-runner` for LLM, `jobs-runner` for Supabase writes). Use Workload Identity Federation for CI/CD.
- **Stripe keys**: store secret keys in Secret Manager; grant read access only to the webhooks service.

## Webhooks & OAuth

- All inbound webhooks (Garmin, Withings, Stripe) are HMAC verified. Ensure secrets (`GARMIN_WEBHOOK_SECRET`, `WITHINGS_WEBHOOK_SECRET`, `STRIPE_WEBHOOK_SECRET`) match vendor dashboards.
- Tunnel local testing through `ngrok` or `cloudflared` with HTTPS. Reset secrets immediately after demos.
- Encrypt provider tokens at rest. Switch placeholder storage to Supabase Vault or Google Secret Manager before production launch.

## Supabase RLS

- Tables under `supabase/sql/rls_policies.sql` enforce per-user isolation. Run `pnpm test` and `supabase db diff` after schema changes to validate policies remain intact.
- Use `withRLS` helper for server actions to keep filters consistent.
- Admin operations (seed scripts, migrations) rely on the service role; run them from trusted environments only.

## Logging & Monitoring

- All services emit structured JSON logs with request IDs—pipe them to Cloud Logging and configure log-based metrics for 4xx/5xx spikes.
- PII is redacted from logs by default. Avoid logging request bodies unless explicitly needed for debugging.

## Dependency Hygiene

- Run `pnpm audit` in CI (add as an optional step). Keep `pnpm-lock.yaml` up to date and renovate dependencies regularly.
- Enable Dependabot or Renovate for GitHub security advisories.

## Secure Development Practices

- Enforce branch protection + required status checks (GitHub Actions workflows in `.github/workflows`).
- Require code review by at least one maintainer for changes touching authentication, billing, or webhook handlers.
- Run Vitest and linting locally before pushing to reduce CI churn.

## Incident Response

- Configure alert routing (PagerDuty, Slack) for Cloud Monitoring alerts (LLM errors, webhook failures, Stripe failures).
- Maintain a runbook describing how to rotate keys, disable checkout, and replay webhooks (`services/webhooks` stores payloads in GCS).

By following these guidelines the project remains compliant with GDPR-friendly practices and Stripe/Supabase security expectations.
