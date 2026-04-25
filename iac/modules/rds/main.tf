resource "random_password" "db" {
  length  = 24
  special = true
  override_special = "!#$%^&*()-_=+"
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "${var.name_prefix}/rds/credentials"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    host     = aws_db_instance.main.address
    port     = 5432
    dbname   = var.db_name
  })
}

resource "aws_db_instance" "main" {
  identifier             = "${var.name_prefix}-rds"
  engine                 = "postgres"
  engine_version         = "16.3"
  instance_class         = "db.t4g.micro"
  allocated_storage      = 20
  storage_type           = "gp3"
  storage_encrypted      = true
  db_name                = var.db_name
  username               = var.db_username
  password               = random_password.db.result
  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  skip_final_snapshot    = true
  backup_retention_period = 1
  apply_immediately      = true

  tags = {
    Name = "${var.name_prefix}-rds"
  }
}
