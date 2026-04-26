variable "lambda_names" { type = list(string) }
variable "state_machine_arn" { type = string }
variable "rds_id" { type = string }
variable "dlq_name" { type = string }
variable "sns_topic_arn" { type = string }
