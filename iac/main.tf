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

module "load_lambda" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-load"
  source_dir    = "${path.module}/../lambdas/load"
  timeout       = 300
  memory_size   = 512

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  dlq_arn = module.sqs.dlq_arn

  inline_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${module.s3.clean_bucket_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = module.rds.secret_arn
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = module.sqs.dlq_arn
      }
    ]
  })
}

module "enrich_lambda" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-enrich"
  source_dir    = "${path.module}/../lambdas/enrich"
  timeout       = 300
  memory_size   = 512

  dlq_arn = module.sqs.dlq_arn

  inline_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${module.s3.clean_bucket_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.region}:*:secret:proptech/openai/*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = module.sqs.dlq_arn
      }
    ]
  })
}

module "transform_lambda" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-transform"
  source_dir    = "${path.module}/../lambdas/transform"
  timeout       = 120

  dlq_arn = module.sqs.dlq_arn

  inline_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${module.s3.raw_bucket_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${module.s3.clean_bucket_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = module.sqs.dlq_arn
      }
    ]
  })
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
