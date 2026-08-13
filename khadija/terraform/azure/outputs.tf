output "subscription_id" {
  description = "The subscription this environment was deployed into — what the scanner reports as account_id."
  value       = data.azurerm_client_config.current.subscription_id
}

output "resource_group_name" {
  description = "The resource group holding every resource in this environment."
  value       = azurerm_resource_group.test.name
}

output "compliant_storage_account_id" {
  description = "The compliant storage account — HTTPS enforced, no anonymous access, TLS 1.2, default-deny firewall."
  value       = module.storage_test_resource.compliant_storage_account_id
}

output "noncompliant_storage_account_id" {
  description = "The intentionally non-compliant storage account — anonymous blob access, plaintext HTTP, TLS 1.0."
  value       = module.storage_test_resource.noncompliant_storage_account_id
}

output "audit_logs_storage_account_id" {
  description = "The private storage account the Activity Log is exported to."
  value       = module.storage_test_resource.audit_logs_storage_account_id
}

output "compliant_nsg_id" {
  description = "The restrictive network security group."
  value       = module.network_test_resource.compliant_nsg_id
}

output "noncompliant_nsg_id" {
  description = "The network security group with SSH and RDP open to the internet."
  value       = module.network_test_resource.noncompliant_nsg_id
}

output "compliant_vm_id" {
  description = "The hardened VM — no public IP, managed identity, restrictive NSG."
  value       = module.compute_test_resource.compliant_vm_id
}

output "noncompliant_vm_id" {
  description = "The soft VM — public IP, no managed identity, internet-open NSG."
  value       = module.compute_test_resource.noncompliant_vm_id
}

output "compliant_key_vault_id" {
  description = "The compliant Key Vault — RBAC, private access, default-deny firewall."
  value       = module.keyvault_test_resource.compliant_key_vault_id
}

output "noncompliant_key_vault_id" {
  description = "The intentionally non-compliant Key Vault — legacy access policies, public access, default-allow firewall."
  value       = module.keyvault_test_resource.noncompliant_key_vault_id
}

output "activity_log_setting_id" {
  description = "The subscription Activity Log diagnostic setting."
  value       = module.monitor_test_resource.activity_log_setting_id
}
