# Zero-Downtime Blue/Green Infrastructure Deployment
Implement a blue/green deployment pattern for infrastructure using Terraform with ALB target group switching, weighted Route53 records, and create_before_destroy lifecycle rules for zero-downtime releases.

## Learning Objectives
- Understand the blue/green deployment pattern applied to infrastructure
- Build parallel environments (blue and green) with ASG and ALB target groups
- Configure weighted Route53 records for gradual traffic shifting
- Implement create_before_destroy lifecycle rules for safe resource replacement
- Shift traffic by updating ALB listener rules and weights
- Execute rollback procedures by swapping traffic weights back
- Verify zero-downtime deployment flow end to end

## Prerequisites
- Completed earlier Terraform scenarios (modules, state management, ASG with ALB)
- Understanding of AWS ALB, target groups, and listener rules
- Familiarity with Route53 weighted routing policies
- Knowledge of Auto Scaling Groups and launch templates

## Resources Created
- ALB with listener rules and two target groups (blue and green)
- Two Auto Scaling Groups (blue and green) with launch templates
- Route53 weighted DNS records for traffic splitting
- Security groups for ALB and instances
- Lifecycle rules with create_before_destroy on key resources

## Cleanup
Run the cleanup command (last step) to remove all resources.
