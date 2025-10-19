output "artifact_registry_repo" {
  value = google_artifact_registry_repository.services.id
}

output "service_account_email" {
  value = google_service_account.cloud_run.email
}

output "webhooks_url" {
  value = google_cloud_run_service.webhooks.status[0].url
}

output "jobs_url" {
  value = google_cloud_run_service.jobs.status[0].url
}

output "llm_url" {
  value = google_cloud_run_service.llm.status[0].url
}

output "pubsub_topic" {
  value = google_pubsub_topic.daily_metrics.name
}
