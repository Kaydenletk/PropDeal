resource "aws_sns_topic_subscription" "email" {
  topic_arn = var.sns_topic_arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name_prefix}-pipeline"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title = "Lambda Invocations"
          metrics = [
            for name in var.lambda_function_names :
            ["AWS/Lambda", "Invocations", "FunctionName", name]
          ]
          period = 300
          stat   = "Sum"
          region = var.region
        }
      },
      {
        type = "metric"
        properties = {
          title = "Lambda Errors"
          metrics = [
            for name in var.lambda_function_names :
            ["AWS/Lambda", "Errors", "FunctionName", name]
          ]
          period = 300
          stat   = "Sum"
          region = var.region
        }
      },
      {
        type = "metric"
        properties = {
          title   = "RDS CPU"
          metrics = [["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.db_identifier]]
          period  = 300
          stat    = "Average"
          region  = var.region
        }
      },
      {
        type = "metric"
        properties = {
          title = "Step Functions Executions"
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", var.state_machine_arn],
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", var.state_machine_arn],
          ]
          period = 300
          stat   = "Sum"
          region = var.region
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each            = toset(var.lambda_function_names)
  alarm_name          = "${each.key}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  dimensions = {
    FunctionName = each.key
  }
  alarm_actions = [var.sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "sfn_failures" {
  alarm_name          = "${var.name_prefix}-sfn-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  dimensions = {
    StateMachineArn = var.state_machine_arn
  }
  alarm_actions = [var.sns_topic_arn]
}
