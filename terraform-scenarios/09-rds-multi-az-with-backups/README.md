# RDS Multi-AZ with Automated Backups
Production-grade RDS deployment with Multi-AZ failover, automated backups, parameter groups, and secure password management via SSM Parameter Store.

## Learning Objectives
- Create DB subnet groups for multi-AZ RDS placement
- Configure custom parameter groups for database tuning
- Deploy an RDS instance with Multi-AZ for high availability
- Set up automated backup retention and maintenance windows
- Store database credentials securely in SSM Parameter Store
- Create read replicas for scaling read-heavy workloads
- Understand the full production RDS architecture

## Prerequisites
- Basic Terraform knowledge (variables, resources, outputs)
- Understanding of AWS VPC and subnets
- Familiarity with relational databases (PostgreSQL/MySQL)
- Completion of VPC scenario recommended

## Resources Created
- DB Subnet Group spanning multiple availability zones
- Custom DB Parameter Group with tuned settings
- RDS Primary Instance with Multi-AZ enabled
- Automated backup configuration with retention policy
- SSM Parameter Store entry for database password
- RDS Read Replica in a separate AZ
- Security group for database access control

## Cleanup
The final step removes all simulated Terraform resources and displayed configurations.
