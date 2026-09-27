terraform {
  required_version = ">= 1.7"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}

variable "resource_group_name" { type = string }
variable "container_app_environment_id" {
  type        = string
  description = "Existing internal Container Apps environment"
}
variable "user_assigned_identity_id" { type = string }
variable "key_vault_secret_id" {
  type        = string
  description = "Existing Key Vault secret URL; identity needs Get permission"
}
variable "image" { type = string }
variable "registry_server" {
  type        = string
  description = "Existing Azure Container Registry login server"
}

provider "azurerm" {
  features {}
}

resource "azurerm_container_app" "api" {
  name                         = "lumentrail-api"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [var.user_assigned_identity_id]
  }
  registry {
    server   = var.registry_server
    identity = var.user_assigned_identity_id
  }
  secret {
    name                = "api-token"
    identity            = var.user_assigned_identity_id
    key_vault_secret_id = var.key_vault_secret_id
  }
  ingress {
    external_enabled           = false
    target_port                = 8080
    allow_insecure_connections = false
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
  template {
    min_replicas = 0
    max_replicas = 2
    container {
      name   = "api"
      image  = var.image
      cpu    = 0.25
      memory = "0.5Gi"
      env {
        name  = "LUMENTRAIL_BEHIND_TLS_PROXY"
        value = "1"
      }
      env {
        name        = "LUMENTRAIL_API_TOKEN"
        secret_name = "api-token"
      }
    }
  }
  lifecycle {
    ignore_changes = [secret]
  }
}

output "internal_fqdn" { value = azurerm_container_app.api.latest_revision_fqdn }
