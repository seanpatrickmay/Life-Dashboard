#!/usr/bin/env bash
set -euo pipefail

# Usage: ./infra/gcp/provision.sh <PROJECT_ID> <REGION> <GCS_BUCKET_RAW>
# Example: ./infra/gcp/provision.sh my-project us-central1 health-raw-dev

PROJECT_ID="${1:-}"
REGION="${2:-us-central1}"
GCS_BUCKET="${3:-}"
REGISTRY_REPO="life-dashboard-services"
WEBHOOK_SERVICE="life-dashboard-webhooks"
JOBS_SERVICE="life-dashboard-jobs"
LLM_SERVICE="life-dashboard-llm"
PUBSUB_TOPIC="daily-metrics"
SCHEDULER_NAME="recompute-daily"
SERVICE_ACCOUNT="life-dashboard-sa"

if [[ -z "$PROJECT_ID" || -z "$GCS_BUCKET" ]]; then
  echo "Usage: $0 <PROJECT_ID> <REGION> <GCS_BUCKET_RAW>"
  exit 1
fi

gcloud config set project "$PROJECT_ID"

echo "Enabling required APIs..."
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  pubsub.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com

echo "Creating Artifact Registry repository..."
gcloud artifacts repositories create "$REGISTRY_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Container images for Life Dashboard services" \
  --async || echo "Repository may already exist."

echo "Creating service account..."
gcloud iam service-accounts create "$SERVICE_ACCOUNT" \
  --project="$PROJECT_ID" \
  --display-name="Life Dashboard Cloud Run SA" || echo "Service account may already exist."

SA_EMAIL="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Assigning IAM roles..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.serviceAgent" || true
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin" || true
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" || true
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/pubsub.publisher" || true

echo "Creating GCS bucket..."
gsutil mb -p "$PROJECT_ID" -c STANDARD -l "$REGION" "gs://${GCS_BUCKET}" || echo "Bucket may already exist."

echo "Creating Pub/Sub topic..."
gcloud pubsub topics create "$PUBSUB_TOPIC" || echo "Topic may already exist."

echo "Creating Secret Manager placeholders..."
for secret in STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET GARMIN_CLIENT_SECRET WITHINGS_CLIENT_SECRET SUPABASE_SERVICE_ROLE_KEY; do
  gcloud secrets create "$secret" --replication-policy="automatic" || echo "Secret $secret may already exist."
done

echo "Creating Cloud Run services..."
for svc in "$WEBHOOK_SERVICE" "$JOBS_SERVICE" "$LLM_SERVICE"; do
  gcloud run services describe "$svc" --region="$REGION" >/dev/null 2>&1 && continue
  gcloud run deploy "$svc" \
    --region="$REGION" \
    --image="gcr.io/cloudrun/hello" \
    --service-account="$SA_EMAIL" \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCP_LOCATION=${REGION},GCS_BUCKET_RAW=${GCS_BUCKET}" \
    --min-instances=0 \
    --max-instances=5
done

echo "Collecting service URLs..."
WEBHOOK_URL=$(gcloud run services describe "$WEBHOOK_SERVICE" --region="$REGION" --format='value(status.url)')
JOBS_URL=$(gcloud run services describe "$JOBS_SERVICE" --region="$REGION" --format='value(status.url)')
LLM_URL=$(gcloud run services describe "$LLM_SERVICE" --region="$REGION" --format='value(status.url)')

echo "Creating Cloud Scheduler job..."
gcloud scheduler jobs create http "$SCHEDULER_NAME" \
  --schedule="30 8 * * *" \
  --time-zone="America/New_York" \
  --http-method=POST \
  --uri="${JOBS_URL}/recompute" \
  --oidc-service-account-email="${SA_EMAIL}" || echo "Scheduler job may already exist."

cat <<EOF
Provisioning complete.

Artifact Registry repo: ${REGISTRY_REPO} (region ${REGION})
Cloud Run:
  Webhooks: ${WEBHOOK_URL}
  Jobs:     ${JOBS_URL}
  LLM:      ${LLM_URL}
Pub/Sub topic: ${PUBSUB_TOPIC}
Scheduler job: ${SCHEDULER_NAME}
GCS bucket: gs://${GCS_BUCKET}

Next steps:
  # Build and push image
  gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY_REPO}/webhooks services/webhooks

  # Deploy to Cloud Run
  gcloud run deploy ${WEBHOOK_SERVICE} \\
    --region ${REGION} \\
    --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY_REPO}/webhooks \\
    --service-account ${SA_EMAIL} \\
    --set-env-vars GCP_PROJECT_ID=${PROJECT_ID},GCP_LOCATION=${REGION},GCS_BUCKET_RAW=${GCS_BUCKET}
EOF
