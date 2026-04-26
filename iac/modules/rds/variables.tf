variable "name_prefix" {
  type = string
}

variable "db_subnet_group_name" {
  type = string
}

variable "security_group_id" {
  type = string
}

variable "db_name" {
  type    = string
  default = "propdeal"
}

variable "db_username" {
  type    = string
  default = "propdeal_admin"
}
