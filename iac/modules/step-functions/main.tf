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
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = var.lambda_arns
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = var.sns_topic_arn
      }
    ]
  })
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.name_prefix}-pipeline"
  role_arn = aws_iam_role.sfn.arn

  definition = templatefile("${path.module}/../../asl/pipeline.json", {
    fetch_arn     = var.fetch_lambda_arn
    transform_arn = var.transform_lambda_arn
    enrich_arn    = var.enrich_lambda_arn
    load_arn      = var.load_lambda_arn
    sns_topic_arn = var.sns_topic_arn
    raw_bucket    = var.raw_bucket
    clean_bucket  = var.clean_bucket
  })

  tracing_configuration {
    enabled = true
  }
}
