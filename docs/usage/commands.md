---
layout: default
title: Commands
parent: Usage
nav_order: 1
---

# Commands

AWS Orga Deployer is a Python package that exposes a command-line interface:

```bash
aws-orga-deployer [common_arguments] <command> [command_arguments]
```

* [Arguments common to all commands](#arguments-common-to-all-commands)
* [Command `orga`](#command-orga)
* [Command `list`](#command-list)
* [Command `preview`](#command-preview)
* [Command `apply`](#command-apply)
* [Command `update-hash`](#command-update-hash)
* [How to interrupt commands](#how-to-interrupt-commands)
* [Command examples](#command-examples)

You can use `aws-orga-deployer --help` or `aws-orga-deployer <command> --help` to display help.

## Arguments common to all commands

* `--package-file <filename>` (or `-p <filename>`): Location of the package definition YAML file. Default is `package.yaml`.
* `--output-file <filename>` (or `-o <filename>`): Location of the JSON file to which the command output details are written. Default is `output.json`.
* `--temp-dir <dirname>`: Location of the folder that stores cache and detailed log files. Default is `.aws_orga_deployer`. See [Logging](logging.html).
* `--force-orga-refresh`: Ignore the cache in S3 and force the tool to query AWS Organizations for information on accounts and organizational unit. See [Package persistent data](../packages/content.html#package-persistent-data).
* `--debug` (or `-d`): Increase log verbosity for debugging.

## Command `orga`

Export AWS account list and organization structure to help you obtain consolidated information about your AWS organization and troubleshoot deployment scope issues.

### Command-specific arguments

None.

### Format of the output file

```json
{
    "Accounts": {
        "<AccountId>": {
            "Name": "string",
            "ParentOUs": ["string"],
            "Tags": {
                "<TagKey>": "<TagValue>"
            },
            "EnabledRegions": ["string"]
        }
    },
    "OUs": {
        "<OUId>": {
            "Tags": {
                "<TagKey>": "<TagValue>"
            },
            "Name": "string"
        }
    }
}
```

* `Accounts`:
    * `<AccountId>`: One attribute per active AWS account.
        * `Name`: Account name.
        * `ParentOUs`: List of organizational units to which this account belongs directly or indirectly.
        * `Tags`: List of tags assigned to this account.
        * `EnabledRegions`: List of regions enabled in this account. AWS Orga Deployer will only deploy moules in enabled regions.
* `OUs`:
    * `<OUId>`: One attribute per organizational unit.
        * `Name`: Name of the OU (`root` for the root OU).
        * `Tags`: List of tags assigned to this account.

## Command `list`

List the existing module deployments and the module deployments to create, update or destroy. This command compares the expected module deployments based on the package definition file and the existing module deployments stored in the package state (see [Package persistent data](../packages/content.html#package-persistent-data)). It does not make any queries or changes to AWS resources.

### Command-specific arguments

* `--detailed-exitcode`: Use this arguments to have three different exit code, instead of two:
    * `0` if succeeded with no module deployments to create, update or destroy
    * `1` if an error occured
    * `2` if the command succeeds with at least one module deployment to create, update or destroy
* `--force-update`: By default, modules are redeployed to a given AWS account and region only when the [module hash](../modules/hash.html) or the variables changes. Add this argument to force module redeployment. Warning: this may result in a large number of deployments.
* *Scope filters*: See [Deployment scope filters](#deployment-scope-filters)

### Format of the output file

```json
{
    "PendingChanges | PendingButSkippedChanges": {
        "Create | Update | ConditionalUpdate | Destroy": [
            {
                "Deployment": {
                    "Module": "string",
                    "AccountId": "string",
                    "Region": "string",
                    "AccountName": "string"
                },
                "ModuleConfig": "dict",
                "TargetState": {
                    "Variables": "dict",
                    "VariablesFromOutputs": "dict",
                    "Dependencies": ["dict"],
                    "ModuleHash": "string"
                },
                "CurrentState": {
                    "Variables": "dict",
                    "VariablesFromOutputs": "dict",
                    "Dependencies": ["dict"],
                    "ModuleHash": "string",
                    "Outputs": "dict",
                    "LastChangedTime": "string"
                }
            }
        ]
    },
    "NoChanges": [
        {
            "Deployment": {
                "Module": "string",
                "AccountId": "string",
                "Region": "string",
                "AccountName": "string"
            },
            "ModuleConfig": "dict",
            "CurrentState": {
                "Variables": "dict",
                "VariablesFromOutputs": "dict",
                "Dependencies": ["dict"],
                "ModuleHash": "string",
                "Outputs": "dict",
                "LastChangedTime": "string"
            }
        }
    ]
}
```

* `PendingChanges`: Module deployments with pending changes.
    * `Create`: List of module deployments to create.
        * `Deployment`:
            * `Module`: Name of the module to deploy.
            * `AccountId`: AWS account ID in which the module deployment must be created.
            * `Region`: Region in which the module deployment must be created.
            * `AccountName`: Name of the AWS account.
        * `ModuleConfig`: Dictionary with the configuration used for this module deployment.
        * `TargetState`: Describes the expected state based on the package definition file.
            * `Variables`: Dictionary with variables and their value.
            * `VariablesFromOutputs`: Dictionary with variables valued by the outputs of other deployments.
            * `Dependencies`: List of dependencies on other deployments.
            * `ModuleHash`: Value of the module hash. See [Module hash](../modules/hash.html).
    * `Update`: List of existing module deployments to update. Same as `Create` with the addition of `CurrentState`:
        * `CurrentState`: Describes the state of the module deployment when it was created or updated for the last time.
            * `Variables`: Dictionary with variables and their value.
            * `VariablesFromOutputs`: Dictionary with variables valued by the outputs of other deployments.
            * `Dependencies`: List of dependencies on other deployments.
            * `ModuleHash`: Value of the module hash. See [Module hash](../modules/hash.html).
            * `Outputs`: List of module outputs and their values.
            * `LastChangedTime`: Time when the deployment was created or updated for the last time.
    * `ConditionalUpdate`: List of existing module deployments that may need to be updated if the inputs valued by the outputs of other deployments change. Same as `Update`.
    * `Destroy`: List of existing module deployments to destroy.
* `PendingButSkippedChanges`: Module deployments with pending changes, but they are skipped because of the deployment scope filters. Same content as `PendingChanges`.
* `NoChanges`: Existing module deployments with no changes to be made. Same content as module deployments to destroy in `PendingChanges`.

## Command `preview`

Preview the resources to add, update or delete if the pending module deployments are applied. This command makes queries to AWS but does not make any changes to resources.

{: .note }
> This command is similar to `terraform plan` in Terraform. No changes to resources are made, even if some output message may be misleading. For example, `1 deployments completed, 0 failed, 0 still pending` means that the step consisting in previewing resource changes to be made completed.

### Command-specific arguments

* `--detailed-exitcode`: Use this arguments to have three different exit code, instead of two:
    * `0` if the command succeeded and applying pending deployments would not make any changes to AWS resources
    * `1` if an error occured
    * `2` if the command succeeded and applying pending deployments would make at least one change to AWS resources
* `--force-update`: By default, modules are redeployed to a given AWS account and region only when the [module hash](../modules/hash.html) or the variables changes. Add this argument to force module redeployment. Warning: this may result in a large number of deployments.
* `--non-interactive`: Do not ask to review and confirm the deployment scope by entering `yes`.
* `--keep-deployment-cache`: Keep temporary files created during module deployment to enable troubleshooting. See [Logging](logging.html). By default, these temporary files are deleted.
* *Scope filters*: See [Deployment scope filters](#deployment-scope-filters)

### Format of the output file

```json
{
    "Completed | Failed | Pending": {
        "Create | Update | ConditionalUpdate | Destroy": [
            {
                "Deployment": {
                    "Module": "string",
                    "AccountId": "string",
                    "Region": "string",
                    "AccountName": "string"
                },
                "NbAttempts": "integer",
                "Result": "string",
                "DetailedResults": "dict",
                "ResultedInChanges": "bool"
            }
        ]
    }
}
```

* `Completed | Failed | Pending`: Module deployment preview status. Can be `Pending` if the command is interrupted.
    * `Create | Update | ConditionalUpdate | Destroy`: Pending changes for this module deployment.
        * `Deployment`:
            * `Module`: Name of the module to deploy.
            * `AccountId`: AWS account ID in which the module deployment must be created.
            * `Region`: Region in which the module deployment must be created.
            * `AccountName`: Name of the AWS account.
        * `NbAttempts`: Number of times this step was attempted.
        * `Result`: One-line summary of the result. Only populated if the action is `Completed` or `Failed`.
        * `DetailedResults`: Optional dictionary that may provide additional information (e.g. list of resources to change, detailed error message). Can only be populated if the action is `Completed` or `Failed`.
        * `ResultedInChanges`: Indicates whether applying pending changes for this deployment would result in resource changes. Only populated if the status is `Completed`.

## Command `apply`

Apply pending module deployments. This command is equivalent to `terraform apply` in Terraform. This package state may be updated during the execution of this command.

### Command-specific arguments

* `--detailed-exitcode`: Use this arguments to have three different exit code, instead of two:
    * `0` if the command succeeded and no changes to AWS resources were made
    * `1` if an error occured
    * `2` if the command succeeded and at least one change to AWS resources was made
* `--force-update`: By default, modules are redeployed to a given AWS account and region only when the [module hash](../modules/hash.html) or the variables changes. Add this argument to force module redeployment. Warning: this may result in a large number of deployments.
* `--non-interactive`: Do not ask to review and confirm the deployment scope by entering `yes`.
* `--keep-deployment-cache`: Keep temporary files created during module deployment to enable troubleshooting. See [Logging](logging.html). By default, these temporary files are deleted.
* `--save-state-every-seconds`: Save the package state periodically to S3 during execution. Specify a value in seconds larger than zero. This automatic saving enables to recover from an eventual crash of AWS Orga Deployer without losing the information that certain deployments may have completed since the beginning of the execution. However, if the execution of the `apply` command takes a lot of time, this can lead to a large number of object versions in S3. In any case, the package state is saved at the end of the execution.
* *Scope filters*: See [Deployment scope filters](#deployment-scope-filters)

### Format of the output file

```json
{
    "Completed | Failed | Pending": {
        "Create | Update | ConditionalUpdate | Destroy": [
            {
                "Deployment": {
                    "Module": "string",
                    "AccountId": "string",
                    "Region": "string",
                    "AccountName": "string"
                },
                "NbAttempts": "integer",
                "Result": "string",
                "DetailedResults": "dict",
                "ResultedInChanges": "bool",
                "Outputs": "dict"
            }
        ]
    }
}
```

* `Completed | Failed | Pending`: Module deployment apply status. Can be `Pending` if the command is interrupted.
    * `Create | Update | ConditionalUpdate | Destroy`: Action made for this module deployment.
        * `Deployment`:
            * `Module`: Name of the module to deploy.
            * `AccountId`: AWS account ID in which the module deployment was made.
            * `Region`: Region in which the module deployment was made.
            * `AccountName`: Name of the AWS account.
        * `NbAttempts`: Number of times this step was attempted.
        * `Result`: One-line summary of the result. Only populated if the action is `Completed` or `Failed`.
        * `DetailedResults`: Optional dictionary that may provide additional information (e.g. list of resources that changed, detailed error message). Can only be populated if the action is `Completed` or `Failed`.
        * `ResultedInChanges`: Indicates this deployment resulted in resource changes. Only populated if the status is `Completed`.
        * `Outputs`: List of outputs. Only populated if the status is `Completed`, and the action is `Create`, `Update` or `ConditionalUpdate`.

## Command `update-hash`

Update the value of the [module hash](../modules/hash.html) in the current state, without making any resource changes. This is useful to edit the module source code (e.g. commenting your code) without needing to update module deployments.

### Command-specific arguments

* `--detailed-exitcode`: Use this arguments to have three different exit code, instead of two:
    * `0` if the command succeeded and no module hash was updated
    * `1` if an error occured
    * `2` if the command succeeded and at least one module hash was updated
* `--force-update`: Not useful for this command.
* `--non-interactive`: Do not ask to review and confirm the deployment scope by entering `yes`.
* `--keep-deployment-cache`: Keep temporary files created during module deployment to enable troubleshooting. See [Logging](logging.html). By default, these temporary files are deleted.
* `--save-state-every-seconds`: Save the package state periodically to S3 during execution. Specify a value in seconds larger than zero. This automatic saving enables to recover from an eventual crash of AWS Orga Deployer without losing the information that certain deployments may have completed since the beginning of the execution. However, if the execution of the `upate-hash` command takes a lot of time, this can lead to a large number of object versions in S3. In any case, the package state is saved at the end of the execution.
* *Scope filters*: See [Deployment scope filters](#deployment-scope-filters)

### Format of the output file

Same as the command `preview`.

## Deployment scope filters

The following arguments enables to restrict the deployment scope to the intersection between the scope defined by these CLI filters and the scope defined in the package definition file.

Notes:

* These arguments can be passed multiple times to provide multiple values.
* The arguments are cumulative. For example, `--include-ou-ids "ou-12345" --include-account-names "*-prod" --exclude-account-names "excluded-prod"` corresponds to all AWS accounts in the OU `ou-12345` whose name ends with `-prod` except `excluded-prod`.
* If no filter arguments are provided, the default scope defined by the CLI filters corresponds to all active AWS accounts and all enabled regions for each account.

Arguments:

* `--include-modules <MODULE>`: Filter the deployment scope by including certain modules only.
* `--include-account-ids <ACCOUNT_ID>`: Filter the deployment scope by including certain AWS account IDs only.
* `--include-account-tags <TAG_KEY=TAG_VALUE>`: Filter the deployment scope by including the AWS accounts with certain tags only. Tags are cumulative, i.e. `KEY1=VALUE1` and `KEY2=VALUE2` includes accounts with a tag `KEY1` = `VALUE1` and with a tag `TAG2` = `VALUE2`.
* `--include-account-names <ACCOUNT_NAME>`: Filter the deployment scope by including certain AWS account names only. You can include wildcards (`*`) like `*-prod`.
* `--include-ou-ids <OU_ID>`: Filter the deployment scope by including the accounts that belong to certain organizational unit IDs only.
* `--include-ou-tags <TAG_KEY=TAG_VALUE>`: Filter the deployment scope by including the AWS accounts that belong to the organizational units with certain tags only. Tags are cumulative, i.e. `KEY1=VALUE1` and `KEY2=VALUE2` includes OUs with a tag `KEY1` = `VALUE1` and with a tag `TAG2` = `VALUE2`.
* `--include-regions <REGION>`: Filter the deployment scope by excluding certain regions.
* `--exclude-modules <MODULE>`: Filter the deployment scope by excluding certain modules.
* `--exclude-account-ids <ACCOUNT_ID>`: Filter the deployment scope by excluding certain AWS account IDs.
* `--exclude-account-tags <TAG_KEY=TAG_VALUE>`: Filter the deployment scope by excluding the AWS accounts with certain tags. Tags are cumulative, i.e. `KEY1=VALUE1` and `KEY2=VALUE2` includes accounts with a tag `KEY1` = `VALUE1` and with a tag `TAG2` = `VALUE2`.
* `--exclude-account-names <ACCOUNT_NAME>`: Filter the deployment scope by excluding certain AWS account names. You can include wildcards (`*`) like `*-prod`.
* `--exclude-ou-ids <OU_ID>`: Filter the deployment scope by excluding the accounts that belong to certain organizational unit IDs.
* `--exclude-ou-tags <TAG_KEY=TAG_VALUE>`: Filter the deployment scope by excluding the AWS accounts that belong to the organizational units with certain tags. Tags are cumulative, i.e. `KEY1=VALUE1` and `KEY2=VALUE2` includes OUs with a tag `KEY1` = `VALUE1` and with a tag `TAG2` = `VALUE2`.
* `--exclude-regions <REGION>`: Filter the deployment scope by excluding certain regions.

## How to interrupt commands

You can press `Ctrl+C` to interrupt a running command.

* The first time you press `Ctrl+C`: AWS Orga Deployer waits for ongoing deployments to complete and exits.
* The second time you press `Ctrl+C`: AWS Orga Deployer sends a `SIGINT` signal to the ongoing deployments, waits for them to complete and exits.
* The third time you press `Ctrl+C`: AWS Orga Deployer sends a `SIGTERM` signal to the ongoing deployments, waits for them to complete and exits.
* The fourth time you press `Ctrl+C`: AWS Orga Deployer exits immediately.

## Command examples

`aws-orga-deployer -d list --include-modules module1`: List the module deployments to create, update or destroy for `module1` only. All other pending deployments are marked as skipped. Debugging logs are displayed.

`aws-orga-deployer apply --include-account-names test-account --non-interactive --detailed-exitcode`: Apply pending module deployments in the account `test-account` only, and return an exit code that allows to identify whether changes were made or not. This can be useful in a CI/CD pipeline to test changes to your package definition file or modules before applying to all other accounts.

`aws-orga-deployer preview --include-account-names test-account --force-update`: Evaluate which resources need to be added, updated or deleted in the account `test-account`, including for module deployments whose module code or variables didn't change.
