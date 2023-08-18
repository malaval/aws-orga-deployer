---
title: Home
layout: home
nav_order: 0
---

# AWS Orga Deployer

## Introduction

AWS Orga Deployer makes it easier to deploy and manage infrastructure-as-code at the scale of an AWS organization. It enables to deploy Terraform or CloudFormation templates and to execute Python scripts in multiple AWS accounts and multiple regions, making it particularly suitable for building AWS foundations (or Landing Zones).

To get started, develop modules (Terraform or CloudFormation templates or Python scripts), create a package definition file to specify which modules to deploy in which accounts and regions and using which parameters, and let AWS Orga Deployer deploy modules and manage dependencies between deployments.

## Installation

AWS Orga Deployer is a Python package with a command-line interface. To install it and check that it works:

```bash
pip install aws-orga-deployer
aws-orga-deployer --help
```

## How it differs from other tools

* Support for Terraform, CloudFormation and Python modules. AWS Orga Deployer lets you manage dependencies between modules and use output values as inputs to other module deployments, even with modules from different types.
* Integration with AWS Organizations to retrieve dynamically the list of accounts and organizational units. AWS Orga Deployer allows to define a list of accounts and regions where each module must be deployed using many inclusion or exclusion criteria, and specify different parameters for each scope (e.g. different retention policy between production and non-production accounts).
* Maintains the state of a package that contains the list of existing module deployments and their parameters, which makes it much faster to evaluate which module deployments must be created, updated or destroyed, even with large AWS organizations.

## Next steps

To start using AWS Orga Deployer, go to the page [Getting Started](getting-started.html).
