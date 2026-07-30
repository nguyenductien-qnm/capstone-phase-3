# Sandbox environment

This directory is the Terraform root module for the current non-production
environment. Run `terraform init`, `plan` and `apply` from this directory.

The remote-state key remains `dev/terraform.tfstate` to preserve the existing
state location during the repository reorganization.
