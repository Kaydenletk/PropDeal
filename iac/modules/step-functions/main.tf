resource "aws_iam_role" "sfn" {
  name = "${var.name_prefix}-sfn-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "sfn" {
  role = aws_iam_role.sfn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = var.lambda_arns
    }]
  })
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.name_prefix}-pipeline"
  role_arn = aws_iam_role.sfn.arn

  definition = jsonencode({
    Comment = "Nightly real estate ingest pipeline"
    StartAt = "Fetch"
    States = {
      Fetch = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.fetch_lambda_arn
          Payload = {
            city  = "San Antonio"
            state = "TX"
          }
        }
        ResultSelector = {
          "s3_key.$"   = "$.Payload.s3_key"
          "raw_bucket" = var.raw_bucket
        }
        Retry = [{
          ErrorEquals     = ["States.ALL"]
          IntervalSeconds = 10
          MaxAttempts     = 2
          BackoffRate     = 2.0
        }]
        Next = "Transform"
      }
      Transform = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.transform_lambda_arn
          Payload = {
            "raw_bucket.$"  = "$.raw_bucket"
            "raw_key.$"     = "$.s3_key"
            "clean_bucket"  = var.clean_bucket
          }
        }
        ResultSelector = {
          "clean_bucket.$" = "$.Payload.clean_bucket"
          "clean_key.$"    = "$.Payload.clean_key"
        }
        Next = "Enrich"
      }
      Enrich = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.enrich_lambda_arn
          "Payload.$"  = "$"
        }
        ResultSelector = {
          "clean_bucket.$" = "$.Payload.clean_bucket"
          "enriched_key.$" = "$.Payload.enriched_key"
        }
        Next = "Load"
      }
      Load = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.load_lambda_arn
          "Payload.$"  = "$"
        }
        End = true
      }
    }
  })

  tracing_configuration {
    enabled = true
  }
}
