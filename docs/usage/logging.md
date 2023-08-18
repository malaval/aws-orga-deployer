---
layout: default
title: Logging
parent: Usage
nav_order: 2
---

# Logging

AWS Orga Deployer uses a temporary directory to store logs and cache. By default, this temporary directory is named `.aws-orga-deployer` and is created in your current working directory. However, you can choose a different location using the CLI argument `--temp-dir`.

This temporary directory is structured as follows:

```text
.aws-orga-deployer/
    logs/
        YYYYMMDD-HHMMSS/
            <moduleName>/
                <AccountId>/
                    <Region>/
                        stderr.log
                        stdout.log
    cache/
        engines/
            <engineName>/
        deployments/
            <moduleName>/
                <AccountId>/
                    <Region>/
```

* `logs`: You can find the execution logs of each module deployments in this folder. For example, the output of the Terraform commands that AWS Orga Deployer makes are available in the `stdout.log` files.
* `cache`:
    * `engines`: Stores cache data specific to each engine that can be reused across all module deployments. For example, Terraform plugins are stored in this folder to avoid downloading one copy of the plugins for each module deployment.
    * `deployments`: Stores cache data specific to each module deployment. For example, folders related to Terraform module deployments contain all `.tf` and `.tfvars` that are passed as input to Terraform. By default, this directory is deleted after each run. If you want to keep it for troubleshooting purposes, use the CLI argument `--keep-deployment-cache`.
