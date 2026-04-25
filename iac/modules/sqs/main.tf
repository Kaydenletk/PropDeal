resource "aws_sqs_queue" "dlq" {
  name                       = "${var.name_prefix}-pipeline-dlq"
  message_retention_seconds  = 1209600  # 14 days
  sqs_managed_sse_enabled    = true

  tags = {
    Name = "${var.name_prefix}-pipeline-dlq"
  }
}
