# State Surgery: Import, Move, and Replace
Master Terraform state manipulation techniques including importing existing resources, moving resources between modules, and forcing resource replacement.

## Learning Objectives
- Understand when state surgery is needed (ClickOps resources, refactoring)
- Use terraform import to bring existing infrastructure under Terraform management
- Use import blocks (Terraform 1.5+) for declarative imports
- Refactor modules safely with terraform state mv and moved blocks
- Force resource recreation with replace_triggered_by
- Remove resources from state without destroying them using terraform state rm

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible

## Resources Created
- Simulated S3 bucket created outside Terraform (ClickOps example)
- Import block configuration for declarative import
- Module refactoring examples with moved blocks
- Lifecycle configuration with replace_triggered_by

## Cleanup
Run the cleanup command (last step) to remove all resources.
