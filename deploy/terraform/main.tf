# Terraform configuration for Sentinela BD Detection System
# GCP Infrastructure as Code

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  # Estado remoto (recomendado para produção)
  backend "gcs" {
    bucket = "sz-wsp-00009-terraform-state"
    prefix = "sentinela-detection"
  }
}

# Provider configuration
provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "sz-wsp-00009"
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "sentinela-detection"
}

variable "dataset_id" {
  description = "BigQuery dataset ID"
  type        = string
  default     = "sentinela_bd"
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudscheduler.googleapis.com", 
    "bigquery.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com"
  ])

  service = each.value
  disable_on_destroy = false
}

# Service Account for Cloud Run
resource "google_service_account" "sentinela_sa" {
  account_id   = "sentinela-detection-sa"
  display_name = "Sentinela Detection Service Account"
  description  = "Service Account para sistema de detecção de desvios"
}

# IAM roles for Service Account
resource "google_project_iam_member" "sentinela_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser", 
    "roles/monitoring.metricWriter",
    "roles/logging.logWriter"
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.sentinela_sa.email}"
}

# BigQuery Dataset
resource "google_bigquery_dataset" "sentinela_dataset" {
  dataset_id = var.dataset_id
  location   = "US"

  description                     = "Dataset para sistema de detecção de desvios Sentinela BD"
  default_table_expiration_ms     = 31536000000 # 1 year
  delete_contents_on_destroy      = false
  
  access {
    role          = "OWNER"
    user_by_email = google_service_account.sentinela_sa.email
  }

  depends_on = [google_project_service.required_apis]
}

# BigQuery Tables
resource "google_bigquery_table" "veiculos_ativos" {
  dataset_id = google_bigquery_dataset.sentinela_dataset.dataset_id
  table_id   = "veiculos_ativos"
  
  description = "Registro horário de veículos ativos nos POIs monitorados"

  time_partitioning {
    type  = "DAY"
    field = "timestamp_verificacao"
    expiration_ms = 31536000000 # 1 year
  }

  clustering = ["filial", "grupo", "status_sla"]

  schema = file("${path.module}/schemas/veiculos_ativos.json")
}

resource "google_bigquery_table" "eventos_desvio" {
  dataset_id = google_bigquery_dataset.sentinela_dataset.dataset_id
  table_id   = "eventos_desvio"
  
  description = "Eventos de desvio de SLA com níveis de escalonamento N1-N4"

  time_partitioning {
    type  = "DAY" 
    field = "timestamp_verificacao"
    expiration_ms = 31536000000 # 1 year
  }

  clustering = ["filial", "grupo", "nivel_alerta", "status_evento"]

  schema = file("${path.module}/schemas/eventos_desvio.json")
}

resource "google_bigquery_table" "escalacoes_niveis" {
  dataset_id = google_bigquery_dataset.sentinela_dataset.dataset_id
  table_id   = "escalacoes_niveis"
  
  description = "Controle de escalonamento de desvios com persistência de estado"

  time_partitioning {
    type  = "DAY"
    field = "timestamp_inicio_desvio" 
    expiration_ms = 31536000000 # 1 year
  }

  clustering = ["filial", "grupo", "nivel_atual", "status"]

  schema = file("${path.module}/schemas/escalacoes_niveis.json")
}

resource "google_bigquery_table" "metricas_sla" {
  dataset_id = google_bigquery_dataset.sentinela_dataset.dataset_id
  table_id   = "metricas_sla"
  
  description = "Métricas consolidadas de SLA por hora"

  time_partitioning {
    type  = "DAY"
    field = "data_verificacao"
    expiration_ms = 7776000000 # 90 days
  }

  clustering = ["filial", "grupo", "em_desvio"]

  schema = file("${path.module}/schemas/metricas_sla.json")
}

resource "google_bigquery_table" "system_logs" {
  dataset_id = google_bigquery_dataset.sentinela_dataset.dataset_id
  table_id   = "system_logs"
  
  description = "Logs estruturados do sistema"

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
    expiration_ms = 2592000000 # 30 days
  }

  clustering = ["log_level", "component"]

  schema = file("${path.module}/schemas/system_logs.json")
}

# Secret for API credentials (placeholder)
resource "google_secret_manager_secret" "api_credentials" {
  secret_id = "frotalog-api-credentials"
  
  replication {
    automatic = true
  }
}

# Secret version (needs to be populated manually)
resource "google_secret_manager_secret_version" "api_credentials_version" {
  secret = google_secret_manager_secret.api_credentials.id
  
  secret_data = jsonencode({
    client_id     = "56963"
    client_secret = "1MSiBaH879w="
  })
}

# IAM for secret access
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  secret_id = google_secret_manager_secret.api_credentials.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sentinela_sa.email}"
}

# Cloud Run Service (will be deployed via gcloud CLI)
# This is a placeholder for reference - actual deployment via PowerShell script
resource "google_cloud_run_service" "sentinela_service" {
  name     = var.service_name
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.sentinela_sa.email
      
      containers {
        image = "gcr.io/${var.project_id}/${var.service_name}:latest"
        
        ports {
          container_port = 8080
        }
        
        resources {
          limits = {
            memory = "1Gi"
            cpu    = "1000m"
          }
        }
        
        env {
          name  = "ENVIRONMENT"
          value = "production"
        }
        
        env {
          name  = "GCP_PROJECT_ID" 
          value = var.project_id
        }
        
        env {
          name  = "BIGQUERY_DATASET"
          value = var.dataset_id
        }
        
        env {
          name = "FROTALOG_CREDENTIALS"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.api_credentials.secret_id
              key  = "latest"
            }
          }
        }
      }
    }
    
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "0"
        "autoscaling.knative.dev/maxScale" = "10"
        "run.googleapis.com/cpu-throttling" = "true"
        "run.googleapis.com/execution-environment" = "gen2"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    google_project_service.required_apis,
    google_bigquery_dataset.sentinela_dataset
  ]
}

# IAM for Cloud Run (allow public access for scheduler)
resource "google_cloud_run_service_iam_member" "invoker" {
  service  = google_cloud_run_service.sentinela_service.name
  location = google_cloud_run_service.sentinela_service.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sentinela_sa.email}"
}

# Cloud Scheduler Job
resource "google_cloud_scheduler_job" "hourly_detection" {
  name        = "sentinela-hourly-detection"
  description = "Execução horária do sistema de detecção de desvios"
  schedule    = "0 * * * *"
  time_zone   = "America/Sao_Paulo"
  
  retry_config {
    retry_count = 3
    max_retry_duration = "60s"
    min_backoff_duration = "5s"
    max_backoff_duration = "30s" 
    max_doublings = 2
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.sentinela_service.status[0].url}/execute"
    
    oidc_token {
      service_account_email = google_service_account.sentinela_sa.email
    }
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      source = "cloud-scheduler"
      timestamp = "{{.timestamp}}"
    }))
  }

  depends_on = [
    google_cloud_run_service.sentinela_service,
    google_project_service.required_apis
  ]
}

# Outputs
output "service_url" {
  description = "URL do Cloud Run service"
  value       = google_cloud_run_service.sentinela_service.status[0].url
}

output "dataset_id" {
  description = "BigQuery Dataset ID"
  value       = google_bigquery_dataset.sentinela_dataset.dataset_id
}

output "service_account_email" {
  description = "Email da service account"
  value       = google_service_account.sentinela_sa.email
}

output "scheduler_job_name" {
  description = "Nome do job do Cloud Scheduler"
  value       = google_cloud_scheduler_job.hourly_detection.name
}