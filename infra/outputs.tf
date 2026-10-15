output "api_url" {
  description = "Public HTTPS endpoint for the FastAPI application."
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "api_fqdn" {
  description = "Fully qualified domain name for API ingress."
  value       = azurerm_container_app.api.ingress[0].fqdn
}

output "acr_name" {
  description = "Name of the Azure Container Registry."
  value       = azurerm_container_registry.main.name
}

output "acr_login_server" {
  description = "ACR login server domain for Docker pushes."
  value       = azurerm_container_registry.main.login_server
}

output "storage_account_name" {
  description = "Name of the Azure Storage Account."
  value       = azurerm_storage_account.main.name
}

output "key_vault_name" {
  description = "Name of the Azure Key Vault."
  value       = azurerm_key_vault.main.name
}

output "postgres_server_fqdn" {
  description = "Fully qualified domain name of PostgreSQL Flexible Server."
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "managed_identity_client_id" {
  description = "Client ID of the User-Assigned Managed Identity."
  value       = azurerm_user_assigned_identity.main.client_id
}

output "managed_identity_id" {
  description = "Resource ID of the User-Assigned Managed Identity."
  value       = azurerm_user_assigned_identity.main.id
}
