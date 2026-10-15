variable "environment" {
  description = "Target deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "location" {
  description = "Azure region for all resources (e.g. eastus, koreacentral, westeurope)."
  type        = string
}

variable "app_prefix" {
  description = "Short prefix for naming resources (3-9 characters, alphanumeric only)."
  type        = string
  default     = "certgen"
  validation {
    condition     = length(var.app_prefix) >= 3 && length(var.app_prefix) <= 9 && can(regex("^[a-zA-Z0-9]+$", var.app_prefix))
    error_message = "app_prefix must be 3-9 alphanumeric characters."
  }
}

variable "db_admin_user" {
  description = "PostgreSQL administrator login username."
  type        = string
  default     = "certadmin"
}

variable "db_admin_password" {
  description = "PostgreSQL administrator password (provide via TF_VAR_db_admin_password or terraform.tfvars)."
  type        = string
  sensitive   = true
}

variable "api_keys" {
  description = "API keys string in key1:user1,key2:user2 format (provide via TF_VAR_api_keys or terraform.tfvars)."
  type        = string
  sensitive   = true
}


variable "api_image" {
  description = "Docker image for FastAPI API container (leave empty to use bulk-cert-gen:latest from deployed ACR)."
  type        = string
  default     = ""
}

variable "worker_image" {
  description = "Docker image for certificate worker (leave empty to use bulk-cert-gen:latest from deployed ACR)."
  type        = string
  default     = ""
}
