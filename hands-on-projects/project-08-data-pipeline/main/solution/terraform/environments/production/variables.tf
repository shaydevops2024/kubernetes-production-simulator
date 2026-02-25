variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used as prefix for all resources"
  type        = string
  default     = "data-pipeline"
}

variable "eks_cluster_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.29"
}

variable "timescaledb_instance_class" {
  description = "RDS instance class for TimescaleDB"
  type        = string
  default     = "db.r6g.large"
}

variable "timescaledb_storage_gb" {
  description = "Storage in GB for TimescaleDB"
  type        = number
  default     = 100
}
