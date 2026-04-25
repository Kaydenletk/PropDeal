# Root composition — modules added in subsequent tasks

module "vpc" {
  source      = "./modules/vpc"
  name_prefix = var.project_name
}
