terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

resource "google_artifact_registry_repository" "services" {
  provider      = google-beta
  location      = var.region
  repository_id = var.artifact_repo
  format        = "DOCKER"
}

resource "google_service_account" "cloud_run" {
  account_id   = var.service_account_id
  display_name = "Life Dashboard Cloud Run SA"
}

resource "google_storage_bucket" "raw" {
  name          = var.gcs_bucket_raw
  location      = var.region
  project       = var.project_id
  force_destroy = false
}

resource "google_pubsub_topic" "daily_metrics" {
  name = var.pubsub_topic
}

locals {
  base_env = {
    GCP_PROJECT_ID = var.project_id
    GCP_LOCATION   = var.region
    GCS_BUCKET_RAW = var.gcs_bucket_raw
  }
}

resource "google_cloud_run_service" "webhooks" {
  name     = var.webhooks_service
  location = var.region

  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "0"
      }
    }

    spec {
      service_account_name = google_service_account.cloud_run.email
      containers {
        image = var.webhooks_image
        env = [for key, value in local.base_env : {
          name  = key
          value = value
        }]
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

resource "google_cloud_run_service" "jobs" {
  name     = var.jobs_service
  location = var.region

  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "0"
      }
    }

    spec {
      service_account_name = google_service_account.cloud_run.email
      containers {
        image = var.jobs_image
        env = [for key, value in local.base_env : {
          name  = key
          value = value
        }]
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

resource "google_cloud_run_service" "llm" {
  name     = var.llm_service
  location = var.region

  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "0"
      }
    }

    spec {
      service_account_name = google_service_account.cloud_run.email
      containers {
        image = var.llm_image
        env = [for key, value in local.base_env : {
          name  = key
          value = value
        }]
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

resource "google_cloud_run_service_iam_member" "webhooks_invoker" {
  service  = google_cloud_run_service.webhooks.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "jobs_invoker" {
  service  = google_cloud_run_service.jobs.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_cloud_run_service_iam_member" "llm_invoker" {
  service  = google_cloud_run_service.llm.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_cloud_scheduler_job" "daily_recompute" {
  name        = var.scheduler_name
  description = "Daily recompute job"
  schedule    = var.scheduler_schedule
  time_zone   = "America/New_York"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.jobs.status[0].url}/recompute"

    oidc_token {
      service_account_email = google_service_account.cloud_run.email
    }
  }
}

resource "google_secret_manager_secret" "secrets" {
  for_each = toset(var.secret_names)

  secret_id = each.key
  replication {
    automatic = true
  }
}

resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
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
