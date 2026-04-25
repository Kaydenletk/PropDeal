# Root composition — modules added in subsequent tasks

module "vpc" {
  source      = "./modules/vpc"
  name_prefix = var.project_name
}

module "s3" {
  source      = "./modules/s3"
  name_prefix = var.project_name
}
