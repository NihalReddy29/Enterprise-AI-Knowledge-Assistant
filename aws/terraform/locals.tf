data "aws_caller_identity" "current" {}

data "aws_vpc" "selected" {
  id      = var.vpc_id != "" ? var.vpc_id : null
  default = var.vpc_id == ""
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.selected.id]
  }

  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  public_subnet_ids = length(var.public_subnet_ids) > 0 ? var.public_subnet_ids : data.aws_subnets.public.ids
  private_subnet_ids = length(var.private_subnet_ids) > 0 ? var.private_subnet_ids : local.public_subnet_ids

  account_id = data.aws_caller_identity.current.account_id
}

resource "random_password" "db" {
  length           = 24
  special          = true
  override_special = "!#$%^&*()-_=+"
}
