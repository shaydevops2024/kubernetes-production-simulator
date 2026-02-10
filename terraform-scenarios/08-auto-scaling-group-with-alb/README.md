# Auto Scaling Group with ALB
Learn how to build a production auto-scaling architecture with launch templates, an Application Load Balancer, target groups, health checks, scaling policies, and rolling update strategies.

## Learning Objectives
- Create a launch template with user_data bootstrap scripts
- Configure an Application Load Balancer with listeners and routing rules
- Set up target groups with health check configurations
- Build an Auto Scaling Group with min, max, and desired capacity
- Connect an ASG to ALB target groups for automatic registration
- Implement CPU-based scaling policies with CloudWatch alarms
- Configure rolling update strategies for zero-downtime deployments

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible

## Resources Created
- EC2 launch template with user_data
- Application Load Balancer with HTTP listener
- Target group with health check configuration
- Auto Scaling Group with capacity settings
- ASG-to-ALB target group attachment
- CPU-based auto scaling policy with CloudWatch alarm
- Rolling update configuration with instance refresh

## Cleanup
Run the cleanup command (last step) to remove all resources.
