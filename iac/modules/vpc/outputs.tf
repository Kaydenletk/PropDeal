output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "public_subnet_id" {
  value = aws_subnet.public.id
}

output "db_subnet_group_name" {
  value = aws_db_subnet_group.main.name
}

output "lambda_security_group_id" {
  value = aws_security_group.lambda.id
}

output "rds_security_group_id" {
  value = aws_security_group.rds.id
}

output "nat_instance_id" {
  value = aws_instance.nat.id
}
