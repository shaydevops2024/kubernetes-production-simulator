# VPC Networking from Scratch
Build a production-ready AWS VPC with public and private subnets, internet gateway, NAT gateway, and route tables across multiple availability zones.

## Learning Objectives
- Create a VPC with a properly sized CIDR block
- Design public and private subnets across availability zones
- Configure an internet gateway for public subnet internet access
- Set up a NAT gateway with Elastic IP for private subnet outbound traffic
- Build route tables and associate them with the correct subnets
- Understand the complete network topology for production workloads

## Prerequisites
- Basic understanding of networking concepts (IP addresses, CIDR notation, subnets)
- Familiarity with Terraform resource syntax and the plan/apply workflow (Scenarios 01-02)

## Resources Created
- VPC with DNS support and hostnames enabled
- Public subnets across three availability zones
- Private subnets across three availability zones
- Internet gateway for public internet access
- NAT gateway with Elastic IP for private outbound traffic
- Public and private route tables with appropriate routes
- Subnet-to-route-table associations

## Cleanup
Run the cleanup command (last step) to remove all resources.
