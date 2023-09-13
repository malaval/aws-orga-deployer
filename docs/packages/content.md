---
layout: default
title: Package content
parent: Packages
nav_order: 0
---

# Package content

## Package definition file

Each package must have a package definition YAML file to specify the package settings, the list of expected module deployments and their configuration.

By default, the package definition file is expected to be located in the current working directory and to be named `package.yaml`. However, another location can be specified by using the `--package-file` (or `-p`) CLI argument.

## Package modules

The files for the modules deployed by a package must be stored in folders located at the same path that the deployment definition file. The first level of folders has the name of the module engine, the second level of folders has the name of the module.

### Example

```text
package.yaml
    python/
        python1/
            main.py
        python2/
            main.py
    terraform/
        terraform1/
            template.tf
            variables.tf
    cloudformation/
        cloudformation1/
            template.yaml
```

This example package has 2 Python modules, 1 Terraform modules and 1 CloudFormation modules.

## Package persistent data

While the package definition file and the package module files can be stored locally or in a code management platform, the package persistent data requires a S3 bucket. If you have multiple packages, you can use the same S3 bucket and use the package name as prefix.

Package persistent data include:

* [Package state](state.html) in `state.json`: Contains the list of module deployed and their configuration at the time they were deployed. This is used to evaluate the list of deployments to create, update or destroy.
* Cached information about AWS accounts and organizational units in `orga.json`: Accelerate the execution of AWS Orga Deployer by removing the need to query AWS Organizations at each run.
* Terraform states for Terraform modules in `terraform/<ModuleName>/<AccountId>/<Region>/terraform.tfstate`.
