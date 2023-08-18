---
layout: default
title: Python
parent: Modules
nav_order: 3
---

# Python

A Python module consists of a custom Python script. The deployment of a Python module consists of executing the script in the context of an AWS account and region. This is notably useful when resources cannot be created or configured using Terraform or CloudFormation.

## How to develop a Python module?

You need at least one file `main.py` with a function `main` in the module directory (`<packageRootDir>/python/<moduleName>`). You are responsible for writing the business logic in `Your code here` based on the inputs passed by AWS Orga Deployer to the function (CLI command executed, lifecycle action, etc.).

```python
def main(
    module,  # str: Name of the module
    account_id,  # str: AWS account ID
    region,  # str: AWS region
    command,  # str: CLI command ("preview" or "apply")
    action,  # str: Action ("create", "update" or "destroy")
    variables,  # dict: Input variables
    module_config,  # dict: Module configuration settings
    module_dir,  # str: Path to the module directory
    deployment_cache_dir,  # str: Path to the temporary directory for the deployment
    engine_cache_dir,  # str: Path to the temporary directory for all Python modules
):

    ################
    # Your code here
    ################
    
    # You must return a tuple of 4 variables:
    # made_changes: bool, True if it resulted in changes made or to be made
    # result: str, One-line summary of the result or error message
    # detailed_results: None or dict, Optional detailed results
    # outputs:
    #   dict, if command is "apply" and action is "create" or "update"
    #   None otherwise
    
    return made_changes, result, detailed_results, outputs
```

## How does it work?

1. AWS Orga Deployer writes deployment inputs (CLI command, deployment action, etc.) into a file named `input.json` stored in the deployment cache directory.
2. AWS Orga Deployer executes a Python script - a *wrapper* - in a subprocess that:
    * Reads the inputs from the file `input.json`. This file allows the main process and the subprocess to communicate.
    * Imports and executes the function `main` of the module file `main.py`.
    * Write the outputs of the function `main` to a file `output.json` in the deployment cache directory.
3. The main process reads the content of the file `output.json` and saves the result.

{: .note }
> If an IAM role is specified in `AssumeRole` for the module configuration, AWS Orga Deployer assumes that role and set the temporary credentials as environment variables of the subprocess. If no role is to be assumed, the subprocess uses the same AWS credentials than the main process.
