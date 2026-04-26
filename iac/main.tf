# Root composition — modules added in subsequent tasks

# Shared SNS topic for both pipeline failure notifications and CloudWatch alarms.
# Defined here (not inside a module) to break the cycle between monitoring (needs
# state_machine_arn) and step-functions (needs sns_topic_arn).
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

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

module "monitoring" {
  source      = "./modules/monitoring"
  name_prefix = var.project_name
  alert_email = var.alert_email
  region      = var.region
  lambda_function_names = [
    module.fetch_lambda.function_name,
    module.transform_lambda.function_name,
    module.enrich_lambda.function_name,
    module.load_lambda.function_name,
    module.api_lambda.function_name,
  ]
  db_identifier     = "${var.project_name}-rds"
  state_machine_arn = module.step_functions.state_machine_arn
  sns_topic_arn     = aws_sns_topic.alerts.arn
}

module "api_lambda" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-api"
  source_dir    = "${path.module}/../lambdas/api/.build"
  timeout       = 30
  memory_size   = 256

  enable_function_url = true

  vpc_config = {
    subnet_ids         = module.vpc.private_subnet_ids
    security_group_ids = [module.vpc.lambda_security_group_id]
  }

  inline_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = module.rds.secret_arn
    }]
  })
}

module "eventbridge" {
  source            = "./modules/eventbridge"
  name_prefix       = var.project_name
  state_machine_arn = module.step_functions.state_machine_arn
}

module "step_functions" {
  source               = "./modules/step-functions"
  name_prefix          = var.project_name
  fetch_lambda_arn     = module.fetch_lambda.function_arn
  transform_lambda_arn = module.transform_lambda.function_arn
  enrich_lambda_arn    = module.enrich_lambda.function_arn
  load_lambda_arn      = module.load_lambda.function_arn
  lambda_arns = [
    module.fetch_lambda.function_arn,
    module.transform_lambda.function_arn,
    module.enrich_lambda.function_arn,
    module.load_lambda.function_arn,
  ]
  raw_bucket    = module.s3.raw_bucket_name
  clean_bucket  = module.s3.clean_bucket_name
  sns_topic_arn = aws_sns_topic.alerts.arn
}

module "load_lambda" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-load"
  source_dir    = "${path.module}/../lambdas/load/.build"
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
  source_dir    = "${path.module}/../lambdas/enrich/.build"
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
  source_dir    = "${path.module}/../lambdas/transform/.build"
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

module "observability" {
  source = "./modules/observability"
  lambda_names = [
    module.fetch_lambda.function_name,
    module.transform_lambda.function_name,
    module.enrich_lambda.function_name,
    module.load_lambda.function_name,
    module.api_lambda.function_name,
  ]
  state_machine_arn = module.step_functions.state_machine_arn
  rds_id            = module.rds.db_instance_id
  dlq_name          = module.sqs.dlq_name
  sns_topic_arn     = aws_sns_topic.alerts.arn
}

module "fetch_lambda" {
  source        = "./modules/lambda"
  function_name = "${var.project_name}-fetch"
  source_dir    = "${path.module}/../lambdas/fetch/.build"
  timeout       = 60
  memory_size   = 256

  environment_variables = {
    RAW_BUCKET           = module.s3.raw_bucket_name
    MAX_LISTINGS_PER_RUN = "30"
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
