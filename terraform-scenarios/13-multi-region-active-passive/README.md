# Multi-Region Active-Passive Infrastructure
Build a production-grade multi-region active-passive architecture with VPC peering, Route53 failover routing, cross-region RDS replicas, and Global Accelerator for high availability.

## Learning Objectives
- Configure multiple AWS provider aliases for multi-region deployments
- Create and peer VPCs across AWS regions
- Set up Route53 failover routing policies for automatic DNS failover
- Deploy cross-region RDS read replicas for database high availability
- Configure AWS Global Accelerator for performance and failover
- Understand active-passive architecture patterns and health checking

## Prerequisites
- Completed earlier Terraform scenarios (modules, state management)
- Understanding of AWS networking (VPCs, subnets, route tables)
- Familiarity with DNS concepts and Route53
- Knowledge of RDS and database replication

## Resources Created
- Two VPCs (primary in us-east-1, secondary in us-west-2)
- VPC peering connection between regions
- Route53 hosted zone with failover routing records
- RDS primary instance and cross-region read replica
- AWS Global Accelerator with endpoint groups
- Health checks for failover triggering
- Security groups and networking in both regions

## Cleanup
Run the cleanup step to remove all displayed example configurations and temporary files.
