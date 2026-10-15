data "azurerm_client_config" "current" {}

# -----------------------------------------------------------------------------
# 1. Resource Group
# -----------------------------------------------------------------------------
resource "random_string" "suffix" {
  length  = 6
  upper   = false
  lower   = true
  numeric = true
  special = false
}

resource "azurerm_resource_group" "main" {
  name     = "${var.app_prefix}-rg-${var.environment}-${random_string.suffix.result}"
  location = var.location
}

locals {
  suffix                = random_string.suffix.result
  name_prefix           = lower(var.app_prefix)
  storage_account_name  = "${local.name_prefix}st${var.environment}${local.suffix}"
  acr_name              = "${local.name_prefix}acr${var.environment}${local.suffix}"
  key_vault_name        = "${local.name_prefix}kv${var.environment}${local.suffix}"
  log_analytics_name    = "${local.name_prefix}-law-${var.environment}-${local.suffix}"
  app_insights_name     = "${local.name_prefix}-ai-${var.environment}-${local.suffix}"
  postgres_server_name  = "${local.name_prefix}-psql-${var.environment}-${local.suffix}"
  managed_identity_name = "${local.name_prefix}-id-${var.environment}-${local.suffix}"
  container_env_name    = "${local.name_prefix}-cae-${var.environment}-${local.suffix}"
  api_app_name          = "${local.name_prefix}-api-${var.environment}-${local.suffix}"
  worker_app_name       = "${local.name_prefix}-worker-${var.environment}-${local.suffix}"

  database_url = "postgresql+asyncpg://${var.db_admin_user}:${urlencode(var.db_admin_password)}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/certificates?ssl=require"

  common_env = [
    { name = "APP_NAME", value = "Bulk Certificate Generator" },
    { name = "ENVIRONMENT", value = var.environment },
    { name = "DATABASE_URL", secret_name = "database-url" },
    { name = "API_KEYS", secret_name = "api-keys" },
    { name = "AZURE_STORAGE_ACCOUNT_NAME", value = azurerm_storage_account.main.name },
    { name = "AZURE_STORAGE_QUEUE_NAME", value = azurerm_storage_queue.jobs.name },
    { name = "AZURE_STORAGE_POISON_QUEUE_NAME", value = azurerm_storage_queue.poison.name },
    { name = "AZURE_STORAGE_UPLOADS_CONTAINER", value = azurerm_storage_container.uploads.name },
    { name = "AZURE_STORAGE_CERTIFICATES_CONTAINER", value = azurerm_storage_container.certificates.name },
    { name = "AZURE_CLIENT_ID", value = azurerm_user_assigned_identity.main.client_id },
    { name = "APPLICATIONINSIGHTS_CONNECTION_STRING", value = azurerm_application_insights.main.connection_string }
  ]
}

# -----------------------------------------------------------------------------
# 2. Managed Identity
# -----------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "main" {
  name                = local.managed_identity_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

# -----------------------------------------------------------------------------
# 3. Observability: Log Analytics & Application Insights
# -----------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = local.log_analytics_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5
}

resource "azurerm_application_insights" "main" {
  name                = local.app_insights_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
}

# -----------------------------------------------------------------------------
# 4. Storage Account
# -----------------------------------------------------------------------------
resource "azurerm_storage_account" "main" {
  name                            = local.storage_account_name
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = false
}

resource "azurerm_storage_container" "uploads" {
  name                  = "uploads"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "certificates" {
  name                  = "certificates"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_queue" "jobs" {
  name               = "certificate-jobs"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_queue" "poison" {
  name               = "certificate-jobs-poison"
  storage_account_id = azurerm_storage_account.main.id
}

# -----------------------------------------------------------------------------
# 5. PostgreSQL Flexible Server
# -----------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server" "main" {
  name                          = local.postgres_server_name
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "16"
  administrator_login           = var.db_admin_user
  administrator_password        = var.db_admin_password
  sku_name                      = "B_Standard_B1ms"
  storage_mb                    = 32768
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  zone                          = "1"
  public_network_access_enabled = true
}

resource "azurerm_postgresql_flexible_server_database" "certificates" {
  name      = "certificates"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
}

# Firewall rule allowing internal Azure Container Apps to communicate with PostgreSQL
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "AllowAllAzureServicesAndResourcesWithinAzureIps"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# -----------------------------------------------------------------------------
# 6. Azure Key Vault
# -----------------------------------------------------------------------------
resource "azurerm_key_vault" "main" {
  name                       = local.key_vault_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = false
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  access_policy {
    tenant_id          = data.azurerm_client_config.current.tenant_id
    object_id          = azurerm_user_assigned_identity.main.principal_id
    secret_permissions = ["Get", "List"]
  }

  access_policy {
    tenant_id          = data.azurerm_client_config.current.tenant_id
    object_id          = data.azurerm_client_config.current.object_id
    secret_permissions = ["Get", "List", "Set", "Delete", "Recover", "Purge"]
  }
}

resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  value        = local.database_url
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_postgresql_flexible_server_database.certificates]
}

resource "azurerm_key_vault_secret" "api_keys" {
  name         = "api-keys"
  value        = var.api_keys
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_key_vault_secret" "storage_connection_string" {
  name         = "storage-connection-string"
  value        = azurerm_storage_account.main.primary_connection_string
  key_vault_id = azurerm_key_vault.main.id
}

# -----------------------------------------------------------------------------
# 7. Azure Container Registry
# -----------------------------------------------------------------------------
resource "azurerm_container_registry" "main" {
  name                = local.acr_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
}

# -----------------------------------------------------------------------------
# 8. Role Assignments for Managed Identity
# -----------------------------------------------------------------------------
resource "azurerm_role_assignment" "blob_contributor" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "queue_contributor" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

# -----------------------------------------------------------------------------
# 9. Azure Container Apps Express (Consumption-only) Environment
# -----------------------------------------------------------------------------

resource "azurerm_container_app_environment" "main" {
  name                       = local.container_env_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  logs_destination           = "log-analytics"
}

# -----------------------------------------------------------------------------
# 10. Azure Container App: API
# -----------------------------------------------------------------------------
resource "azurerm_container_app" "api" {
  name                         = local.api_app_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main.id]
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "database-url"
    value = local.database_url
  }

  secret {
    name  = "api-keys"
    value = var.api_keys
  }

  secret {
    name  = "storage-connection-string"
    value = azurerm_storage_account.main.primary_connection_string
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "auto"
    allow_insecure_connections = false

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 0
    max_replicas = 2

    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = 50
    }

    container {
      name   = "api"
      image  = var.api_image != "" ? var.api_image : "${azurerm_container_registry.main.login_server}/bulk-cert-gen:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      dynamic "env" {
        for_each = local.common_env
        content {
          name        = env.value.name
          value       = try(env.value.value, null)
          secret_name = try(env.value.secret_name, null)
        }
      }

      liveness_probe {
        transport        = "HTTP"
        path             = "/health"
        port             = 8000
        initial_delay    = 10
        interval_seconds = 30
      }

      readiness_probe {
        transport        = "HTTP"
        path             = "/ready"
        port             = 8000
        initial_delay    = 10
        interval_seconds = 15
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.blob_contributor,
    azurerm_role_assignment.queue_contributor,
    azurerm_role_assignment.acr_pull
  ]
}

# -----------------------------------------------------------------------------
# 11. Azure Container App: Worker
# -----------------------------------------------------------------------------
resource "azurerm_container_app" "worker" {
  name                         = local.worker_app_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main.id]
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "database-url"
    value = local.database_url
  }

  secret {
    name  = "api-keys"
    value = var.api_keys
  }

  secret {
    name  = "storage-connection-string"
    value = azurerm_storage_account.main.primary_connection_string
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name    = "worker"
      image   = var.worker_image != "" ? var.worker_image : "${azurerm_container_registry.main.login_server}/bulk-cert-gen:latest"
      cpu     = 0.25
      memory  = "0.5Gi"
      command = ["/app/.venv/bin/python", "-m", "app.worker.main"]
      args    = ["--continuous"]

      dynamic "env" {
        for_each = local.common_env
        content {
          name        = env.value.name
          value       = try(env.value.value, null)
          secret_name = try(env.value.secret_name, null)
        }
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.blob_contributor,
    azurerm_role_assignment.queue_contributor,
    azurerm_role_assignment.acr_pull
  ]
}
