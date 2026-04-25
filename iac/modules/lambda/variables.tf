variable "function_name" {
  type = string
}

variable "source_dir" {
  type = string
}

variable "timeout" {
  type    = number
  default = 60
}

variable "memory_size" {
  type    = number
  default = 256
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "vpc_config" {
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "inline_policy_json" {
  type    = string
  default = null
}

variable "dlq_arn" {
  type    = string
  default = null
}

variable "enable_function_url" {
  type    = bool
  default = false
}
