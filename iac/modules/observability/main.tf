resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "propdeal-pipeline-slo"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [for n in var.lambda_names : ["AWS/Lambda", "Duration", "FunctionName", n, { stat = "p95" }]]
          title   = "Lambda p95 duration"
          region  = "us-east-1"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [for n in var.lambda_names : ["AWS/Lambda", "Errors", "FunctionName", n]]
          title   = "Lambda errors"
          region  = "us-east-1"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", var.state_machine_arn],
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", var.state_machine_arn]
          ]
          title  = "Pipeline success vs fail"
          region = "us-east-1"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_id],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.rds_id]
          ]
          title  = "RDS"
          region = "us-east-1"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.dlq_name]]
          title   = "DLQ depth"
          region  = "us-east-1"
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "pipeline_slo_breach" {
  alarm_name          = "propdeal-pipeline-slo-breach"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsSucceeded"
  namespace           = "AWS/States"
  period              = 86400
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "SLO: 99% pipeline success / 30 days"
  dimensions          = { StateMachineArn = var.state_machine_arn }
  alarm_actions       = [var.sns_topic_arn]
  ok_actions          = [var.sns_topic_arn]
  treat_missing_data  = "breaching"
}
