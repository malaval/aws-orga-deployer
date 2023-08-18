---
layout: default
title: Module hash
parent: Modules
nav_order: 0
---

# Module hash

The module hash is a hash string representation of the files composing a module. If one of the files change, the module hash changes.

The module hash is stored in the package state and is used to compare the current version of the module files with the version that existed when the module deployment was created or updated for the last time. If the module hash differs, AWS Orga Deployer considers that the module deployment needs to be updated.

## Module hash configuration file

By default, the files that are taken into account when calculating the module hash depends on the engine:

* Terraform scripts: All `.tf` files.
* CloudFormation scripts: All `.json` or `.yaml` files.
* Python scripts: All `.py` files.

For example, if the directory of a Python module contain two files - `main.py` and `parameters.csv` - only the file `main.py` is used by default to calculate the module hash.

However, you can create a file `hash-config.json` at the root of the module directory to specify the filename patterns to include and exclude when calculating the module hash. The file must be formatted as follows:

```json
{
    "Include": ["<pattern>"],
    "Exclude": ["<pattern>"]
}
```

For example, the following file specifies that the module hash must be calculated using all `.py` and `.csv` files, except files that are prefixed by `~`:

```json
{
    "Include": ["*.py", "*.csv"],
    "Exclude": ["~*.*"]
}
```

## How can I force module deployments to update?

If you need to update module deployments:

* You can change one of the file that compose the module files (e.g. add a comment) or change the input variables to the module deployment.
* Use the argument `--force-update` in the commands `aws-orga-deployer list|preview|apply` (see [Commands](../usage/commands.html)).

## How can I prevent module deployments from updating after a change in the module code?

If you changed one of the module files but don't want AWS Orga Deployer to update the related module deployments, you can use the commands `aws-orga-deployer update-hash` to update the value of the module hash in the current package state without modifying any of the AWS resources.
