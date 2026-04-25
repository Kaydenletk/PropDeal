variable "name_prefix" { type = string }
variable "alert_email" { type = string }
variable "lambda_function_names" { type = list(string) }
variable "db_identifier" { type = string }
variable "state_machine_arn" { type = string }
variable "region" { type = string }
