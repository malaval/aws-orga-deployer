---
layout: default
title: Other FAQs
parent: Usage
nav_order: 4
---

# Other Frequently Asked Questions

## How to destroy a module deployment?

There is no command like `terraform destroy` in AWS Orga Deployer. To destroy a deployment, you need to update your package definition file to remove the AWS account and region from the scope where the module is deployed. You could also exclude a specific organizational unit, and move the account to that OU in AWS Organizations. Once the package definition file is updated, AWS Orga Deployer will identify that there are deployments to destroy when running the commands `list`, `preview` or `apply`.

## What if I need to close an AWS account?

If you have deployed modules in an account that you need to close, you should use AWS Orga Deployer to destroy the module deployments before closing the account. If the account is closed before destroying exising deployments, AWS Orga Deployer considers that these deployments must be destroyed but these changes are skipped. In that case, you should edit manually the package state (see [Package state](../package/state.html)).
