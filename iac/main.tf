# Root composition — modules added in subsequent tasks

module "vpc" {
  source      = "./modules/vpc"
  name_prefix = var.project_name
}

module "s3" {
  source      = "./modules/s3"
  name_prefix = var.project_name
}

module "rds" {
  source               = "./modules/rds"
  name_prefix          = var.project_name
  db_subnet_group_name = module.vpc.db_subnet_group_name
  security_group_id    = module.vpc.rds_security_group_id
}
