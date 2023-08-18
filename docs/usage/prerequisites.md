---
layout: default
title: Prerequisites
parent: Usage
nav_order: 0
---

# Prerequisites

This page describes the prerequisites that you must meet before you can start using AWS Orga Deployer.

## S3 bucket

You need a S3 bucket to store package persistent data. You can eventually chose to store the data of multiple packages in the same bucket by prefixing objects. When launching AWS Orga Deployer in a terminal, the current AWS credentials must have the following S3 permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::my-bucket",
            "Condition": {
                "StringLike": {
                    "s3:prefix": [
                        "prefix",
                        "prefix/*"
                    ]
                }
            }
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::my-bucket/prefix/*"
        }
    ]
}
```

## Permissions to query AWS Organizations

AWS Orga Deployer needs to query AWS Organizations and the Account API to retrieve information about the AWS accounts and organizational units. AWS Orga Deployer must assume an IAM role in the **AWS management account** with the following permissions (aka. master account) unless your current AWS credentials have already these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "account:ListRegions",
                "organizations:DescribeOrganizationalUnit",
                "organizations:ListAccounts",
                "organizations:ListChildren",
                "organizations:ListRoots",
                "organizations:ListTagsForResource"
            ],
            "Resource": "*"
        }
    ]
}
```

## Permissions to deploy modules

AWS Orga Deployer will need permissions to deploy AWS resources in multiple AWS accounts and regions. You should create an IAM role in all accounts that can be assumed using your current AWS credentials. For example, you can create an IAM role `SecurityAdmin` that can be assumed by your Security account only to deploy security-related resources.

## Terraform

To deploy Terraform resources, you must have Terraform installed.
