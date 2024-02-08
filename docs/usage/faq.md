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

If you have deployed modules in an account that you need to close, you should use AWS Orga Deployer to destroy the module deployments before closing the account.

If the account is closed before destroying exising deployments, AWS Orga Deployer considers that these deployments must be destroyed but these changes are skipped. Note that AWS Orga Deployer will wrongly indicate that the changes are skipped because of CLI arguments, but this is because the included scope by default is all ative accounts. In that case, you should use the command `remove-orphans` to remove orphaned module deployments from the package state.

## How to migrate existing deployments to AWS Orga Deployer?

If you have already created resources using Terraform, CloudFormation or Python scripts outside of AWS Orga Deployer, here is a high-level procedure to migrate to AWS Orga Deployer:

1. Create a package and the necessary modules.
2. Write the package definition file such that the deployments to create match the existing deployments.
3. For:
    * Terraform: Upload the Terraform state of all existing deployments to `s3://<S3Bucket>/<S3Prefix>/terraform/<ModuleName>/<AccountId>/<Region>/terraform.tfstate`
    * CloudFormation: Make sure that the CloudFormation stack already exist.
    * Python: Make sure that the Python scripts have already been executed.
4. Download the package state `state.json` from the S3 bucket.
5. Execute `aws-orga-deployer list`. It should indicate that there are as many deployments to create as there are existing deployments.
6. Open the file `output.json` and for each item in the list at `root["PendingChanges"]["Create"]`:
    1. Copy the item into the list at `root["Deployments"]` of the package state (see [Package state](../package/state.html) for the expected structure).
    2. Remove the attribute `AccountName` in `item["Deployment"]`.
    3. Remove the attribute `item["ModuleConfiguration"]`.
    4. Rename the attribute `item["TargetState"]` by `item["CurrentState"]`.
    5. Add a string attribute `LastChangedTime` in `item["CurrentState"]`.
    6. Add a dict attribute `Outputs` in `item["CurrentState"]`. It must be either an empty dict, or populated with the output values of the deployments.
7. Upload the modified version of the package state `state.json`.
8. Re-execute `aws-orga-deployer list` to check that there are no pending deployments to create.

## Why certain Terraform deployments fail and the error logs in `stderr.log` contain `the cached package for xxx does not match any of the checksums recorded in the dependency lock file`?

Terraform finds and installs providers during the initialization step (`terraform init`). AWS Orga Deployer uses a shared directory to store provider binairies, instead of each deployment downloading and storing its own copy of the providers, to save disk space and network bandwidth.

This error may occur when multiple Terraform deployments are launched simultaneously. If the shared directory doesn't yet contain the required providers, each deployment tries to download and store the provider binairies into the shared directory, leading to concurrency issues. The [Terraform documentation](https://developer.hashicorp.com/terraform/cli/config/config-file) mentions "the plugin cache directory is not guaranteed to be concurrency safe. The provider installer's behavior in environments with multiple terraform init calls is undefined."

If this error occurs, retry the failed tasks. To prevent the error from occuring, disable concurrency during the first execution of the package (set `ConcurrentWorkers: 1` in the package definition file).
