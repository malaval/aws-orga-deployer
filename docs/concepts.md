---
layout: default
title: Concepts
nav_order: 1
---

# Concepts

## Package

A package is a collection of modules to deploy in your AWS accounts. Each package has a [definition file](packages/file.md) that specifies which modules are to be deployed where and with which parameters. You can choose to use a single package to deploy all your modules, or you can split in multiple packages to separate by usage (e.g. security, network, etc.) and by team in charge. For example, you could have one package that creates and maintains all security-related resources in your AWS organization (IAM roles, AWS Config, AWS Security Hub, Amazon GuardDuty, S3 buckets for logging, etc.).

## Engine

An engine is a type of modules that AWS Orga Deployer supports. Currently, there are three supported engines: [Terraform](../modules/terraform.html), [CloudFormation](../modules/cloudformation.html) and [Python](../modules/python.html).

## Module

A module corresponds to a collection of AWS resources to deploy or configure. The nature of a module depends on its engine: a template for Terraform and CloudFormation, a script for Python. You are responsible for developing your modules that AWS Orga Deployer will deploy and execute.

## Module deployment

A module deployment is the instantiation of a module in an AWS account and region. It can be a CloudFormation stack for CloudFormation modules, resulting resources for Terraform modules, or the execution of a script for Python modules.
