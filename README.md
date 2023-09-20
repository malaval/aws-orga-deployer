# AWS Orga Deployer

*Read the documentation: [https://malaval.github.io/aws-orga-deployer](https://malaval.github.io/aws-orga-deployer)*

*Medium story: [https://medium.com/@malavaln/why-i-built-my-own-tool-to-deploy-landing-zones-on-aws-9ed609c1cb25](https://medium.com/@malavaln/why-i-built-my-own-tool-to-deploy-landing-zones-on-aws-9ed609c1cb25)*

## Introduction

AWS Orga Deployer makes it easier to deploy and manage infrastructure-as-code at the scale of an AWS organization. It enables to deploy Terraform or CloudFormation templates and to execute Python scripts in multiple AWS accounts and multiple regions, making it particularly suitable for building AWS foundations (or Landing Zones).

To get started, develop modules (Terraform or CloudFormation templates or Python scripts), create a package definition file to specify which modules to deploy in which accounts and regions and using which parameters, and let AWS Orga Deployer deploy modules and manage dependencies between deployments.

## Installation

AWS Orga Deployer is a Python package with a command-line interface. To install it and check that it works:

```bash
pip install aws-orga-deployer
aws-orga-deployer --help
```

## Documentation

The documentation is available at [https://malaval.github.io/aws-orga-deployer](https://malaval.github.io/aws-orga-deployer). For an example of how to use AWS Orga Deployer,  read the [Getting Started](https://malaval.github.io/aws-orga-deployer/getting-started.html) page.
