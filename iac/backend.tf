terraform {
  backend "s3" {
    bucket         = "propdeal-tfstate-<ACCOUNT_ID>"
    key            = "pipeline/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "propdeal-tflock"
    encrypt        = true
  }
}
