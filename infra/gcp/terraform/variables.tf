variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region (default us-central1)"
  default     = "us-central1"
}

variable "artifact_repo" {
  type        = string
  description = "Artifact Registry repository ID"
  default     = "life-dashboard-services"
}

variable "service_account_id" {
  type        = string
  description = "Service account ID for Cloud Run"
  default     = "life-dashboard-sa"
}

variable "gcs_bucket_raw" {
  type        = string
  description = "Raw payload bucket name"
}

variable "pubsub_topic" {
  type        = string
  description = "Pub/Sub topic for metrics"
  default     = "daily-metrics"
}

variable "webhooks_service" {
  type        = string
  description = "Cloud Run service name for webhooks"
  default     = "life-dashboard-webhooks"
}

variable "jobs_service" {
  type        = string
  description = "Cloud Run service name for jobs"
  default     = "life-dashboard-jobs"
}

variable "llm_service" {
  type        = string
  description = "Cloud Run service name for llm"
  default     = "life-dashboard-llm"
}

variable "webhooks_image" {
  type        = string
  description = "Container image for webhooks service"
}

variable "jobs_image" {
  type        = string
  description = "Container image for jobs service"
}

variable "llm_image" {
  type        = string
  description = "Container image for llm service"
}

variable "scheduler_name" {
  type        = string
  description = "Cloud Scheduler job name"
  default     = "recompute-daily"
}

variable "scheduler_schedule" {
  type        = string
  description = "Cron schedule string"
  default     = "30 8 * * *"
}

variable "secret_names" {
  type        = list(string)
  description = "Secrets to create in Secret Manager"
  default     = [
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "GARMIN_CLIENT_SECRET",
    "WITHINGS_CLIENT_SECRET",
    "SUPABASE_SERVICE_ROLE_KEY"
  ]
}
