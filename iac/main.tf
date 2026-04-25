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

module "sqs" {
  source      = "./modules/sqs"
  name_prefix = var.project_name
}

module "fetch_lambda" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-fetch"
  source_dir    = "${path.module}/../lambdas/fetch"
  timeout       = 60
  memory_size   = 256

  environment_variables = {
    RAW_BUCKET = module.s3.raw_bucket_name
  }

  dlq_arn = module.sqs.dlq_arn

  inline_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${module.s3.raw_bucket_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.region}:*:secret:proptech/rentcast/*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = module.sqs.dlq_arn
      }
    ]
  })
}
