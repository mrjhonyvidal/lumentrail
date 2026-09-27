terraform {
  required_version = ">= 1.7"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 8.0" }
  }
}

variable "project_id" { type = string }
variable "region" { type = string }
variable "image" { type = string }
variable "api_token_secret_id" {
  type        = string
  description = "Existing Secret Manager secret ID containing a random API token"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_service_account" "api" {
  account_id   = "lumentrail-api"
  display_name = "LumenTrail read-only demo"
}

resource "google_secret_manager_secret_iam_member" "api_token" {
  secret_id = var.api_token_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name                = "lumentrail-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = false

  template {
    service_account = google_service_account.api.email
    containers {
      image = var.image
      ports { container_port = 8080 }
      env {
        name  = "LUMENTRAIL_BEHIND_TLS_PROXY"
        value = "1"
      }
      env {
        name = "LUMENTRAIL_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = var.api_token_secret_id
            version = "latest"
          }
        }
      }
      resources { limits = { cpu = "1", memory = "512Mi" } }
    }
    scaling { max_instance_count = 2 }
  }
  depends_on = [google_secret_manager_secret_iam_member.api_token]
}

output "internal_url" { value = google_cloud_run_v2_service.api.uri }
