output "raw_bucket_name" {
  value = aws_s3_bucket.raw.id
}

output "raw_bucket_arn" {
  value = aws_s3_bucket.raw.arn
}

output "clean_bucket_name" {
  value = aws_s3_bucket.clean.id
}

output "clean_bucket_arn" {
  value = aws_s3_bucket.clean.arn
}
