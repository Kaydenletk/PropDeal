# Outputs added as modules wire up

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "api_url" {
  value = module.api_lambda.function_url
}
