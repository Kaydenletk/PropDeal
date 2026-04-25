terraform {
  backend "s3" {
    bucket         = "proptech-tfstate-<ACCOUNT_ID>"
    key            = "pipeline/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "proptech-tflock"
    encrypt        = true
  }
}
