###############################################################################
# Terraform — Production Infrastructure
# Creates: VPC, EKS cluster, RDS (TimescaleDB alternative), S3 for Spark logs
###############################################################################

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
  backend "s3" {
    bucket = "your-terraform-state-bucket"
    key    = "data-pipeline/production/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# ── VPC ───────────────────────────────────────────────────────────────────────
module "vpc" {
  source  = "../../modules/vpc"

  name             = "${var.project_name}-vpc"
  cidr             = "10.0.0.0/16"
  azs              = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets   = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  enable_nat_gateway = true
  single_nat_gateway = false   # HA: one per AZ
  tags             = local.common_tags
}

# ── EKS ───────────────────────────────────────────────────────────────────────
module "eks" {
  source  = "../../modules/eks"

  cluster_name    = "${var.project_name}-eks"
  cluster_version = "1.29"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnet_ids

  node_groups = {
    # General workloads (dashboard, operators)
    general = {
      instance_types = ["m5.large"]
      min_size       = 2
      max_size       = 5
      desired_size   = 2
    }
    # Kafka/Spark workloads — memory optimized
    data = {
      instance_types = ["r5.xlarge"]
      min_size       = 3
      max_size       = 10
      desired_size   = 3
      labels = {
        workload = "data"
      }
      taints = [{
        key    = "workload"
        value  = "data"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  tags = local.common_tags
}

# ── S3: Spark event logs ──────────────────────────────────────────────────────
resource "aws_s3_bucket" "spark_logs" {
  bucket = "${var.project_name}-spark-logs-${random_id.suffix.hex}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_lifecycle_configuration" "spark_logs" {
  bucket = aws_s3_bucket.spark_logs.id
  rule {
    id     = "expire-old-logs"
    status = "Enabled"
    expiration { days = 30 }
  }
}

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  common_tags = {
    Project     = var.project_name
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
