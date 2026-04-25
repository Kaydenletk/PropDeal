variable "name_prefix" { type = string }
variable "fetch_lambda_arn" { type = string }
variable "transform_lambda_arn" { type = string }
variable "enrich_lambda_arn" { type = string }
variable "load_lambda_arn" { type = string }
variable "lambda_arns" { type = list(string) }
variable "raw_bucket" { type = string }
variable "clean_bucket" { type = string }
