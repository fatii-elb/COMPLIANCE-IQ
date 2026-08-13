data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 6
  lower   = true
  upper   = false
  numeric = true
  special = false
}

# One resource group holds the whole environment, so `terraform
# destroy` (or, in the worst case, deleting the group by hand) reliably
# removes every billable resource this module creates.
resource "azurerm_resource_group" "test" {
  name     = "${var.name_prefix}-rg"
  location = var.location
}

module "storage_test_resource" {
  source              = "./modules/storage_test_resource"
  storage_name_prefix = var.storage_name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.test.name
  unique_suffix       = random_string.suffix.result
}

module "network_test_resource" {
  source              = "./modules/network_test_resource"
  name_prefix         = var.name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.test.name
}

module "compute_test_resource" {
  source                 = "./modules/compute_test_resource"
  name_prefix            = var.name_prefix
  location               = var.location
  resource_group_name    = azurerm_resource_group.test.name
  compliant_subnet_id    = module.network_test_resource.compliant_subnet_id
  noncompliant_subnet_id = module.network_test_resource.noncompliant_subnet_id
  admin_ssh_public_key   = var.admin_ssh_public_key
}

module "keyvault_test_resource" {
  source              = "./modules/keyvault_test_resource"
  name_prefix         = var.name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.test.name
  azure_tenant_id     = data.azurerm_client_config.current.tenant_id
  unique_suffix       = random_string.suffix.result
}

module "monitor_test_resource" {
  source             = "./modules/monitor_test_resource"
  name_prefix        = var.name_prefix
  subscription_id    = data.azurerm_client_config.current.subscription_id
  storage_account_id = module.storage_test_resource.audit_logs_storage_account_id
}
