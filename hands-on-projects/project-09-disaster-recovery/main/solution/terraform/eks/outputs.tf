output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS control plane endpoint"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded certificate authority data"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "configure_kubectl" {
  description = "Command to configure kubectl for this cluster"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "velero_bucket_name" {
  description = "S3 bucket name for Velero backups"
  value       = aws_s3_bucket.velero.id
}

output "velero_iam_role_arn" {
  description = "IAM role ARN for Velero (used in Helm values)"
  value       = aws_iam_role.velero.arn
}

output "velero_helm_command" {
  description = "Helm command to install Velero on the EKS cluster"
  value       = <<-EOT
    helm install velero vmware-tanzu/velero \
      --namespace velero \
      --create-namespace \
      --set configuration.backupStorageLocation[0].name=aws \
      --set configuration.backupStorageLocation[0].provider=aws \
      --set configuration.backupStorageLocation[0].bucket=${aws_s3_bucket.velero.id} \
      --set configuration.backupStorageLocation[0].config.region=${var.aws_region} \
      --set serviceAccount.server.annotations."eks\\.amazonaws\\.com/role-arn"=${aws_iam_role.velero.arn} \
      --set credentials.useSecret=false
  EOT
}
