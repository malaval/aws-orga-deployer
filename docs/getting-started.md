---
layout: default
title: Getting started
nav_order: 2
---

# Getting started

## Step 0: Install AWS Orga Deployer

Execute the following command:

```bash
pip install aws-orga-deployer
```

## Step 1: Meet prerequisites

Follow the instructions at [Prerequisites](usage/prerequisites.html) to create a S3 bucket and an IAM role in your AWS management account with permissions to query AWS Organizations.

For the sake of simplicity, we will deploy modules only in your current AWS account and we will assume that your current AWS credentials (in your terminal) have sufficient permissions to create and delete parameters in AWS Systems Manager Parameter Store.

## Step 2: Create a CloudFormation module

Create a new folder for your package. In this folder, create a folder `cloudformation`. In this folder, create a folder `ssm-parameter`. In this folder, create a file `template.yaml` whose content is:

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Parameters:
  SSMParameterValue:
    Type: String
Resources:
  SSMParameter:
    Type: AWS::SSM::Parameter
    Properties:
      Type: String
      Value: !Ref SSMParameterValue
```

The folder structure should look like:

```text
root-folder/
    cloudformation/
        ssm-parameter/
            template.yaml
```

{: .note }
> To go further, you could create additional [Terraform](../modules/terraform.html), [CloudFormation](../modules/cloudformation.html) or [Python](../modules/python.html) modules.

## Step 3: Create a package definition file

In the `root-folder`, create a file `package.yaml` whose content is:

```yaml
PackageConfiguration:
  S3Bucket: "<replace by your bucket name>"
  S3Region: "<replace by your bucket region>"
  AssumeOrgaRoleArn: "<replace by the ARN of the IAM role>"

Modules:
  ssm-parameter:
    Configuration:
      StackName: test-orga-deployer
      TemplateFilename: template.yaml
    Deployments:
      - Include:
          AccountIds:
            - "<replace by your AWS account ID>"
          Regions:
            - eu-west-1
            - us-east-1
        Variables:
          SSMParameterValue: "old-${CURRENT_ACCOUNT_ID}-${CURRENT_REGION}"
```

## Step 4: List the module deployments to create

You will now evaluate the module deployments that AWS Orga Deployer must create, update or delete:

* Change your current working directory to the root folder containing the file `package.yaml`
* Run the following command: `aws-orga-deployer list`
* Check the content of the file `outputs.json` that AWS Orga Deployer generated in the root folder. You should see two deployments.

## Step 5: List the AWS resources to create by the pending deployments

AWS Orga Deployer has not made any requests to AWS yet, besides to query AWS Organizations. This list of module deployments to create is evaluated using the expected state defined by the package definition file, and the current state stored in the package state.

You will now evaluate the resources to add, update or delete if these two module deployments are created:

* Run the following command: `aws-orga-deployer preview`
* Check the content of the file `outputs.json` that AWS Orga Deployer generated in the root folder. You should see that each deployment will create one SSM parameter.

## Step 6: Create the module deployments

You will now create the module deployments:

* Run the following command: `aws-orga-deployer apply`
* Check the content of the file `outputs.json` that AWS Orga Deployer generated in the root folder.
* Check that the CloudFormation stack and SSM parameters exist in your AWS Management Console.
* Run the command `aws-orga-deployer apply` again and check that there are no changes to be made.

## Step 7: Update the module deployments

* Update the file `package.yaml` by:

```yaml
PackageConfiguration:
  S3Bucket: "<replace by your bucket name>"
  S3Region: "<replace by your bucket region>"
  AssumeOrgaRoleArn: "<replace by the ARN of the IAM role>"

Modules:
  ssm-parameter:
    Configuration:
      StackName: test-orga-deployer
      TemplateFilename: template.yaml
    Deployments:
      - Include:
          AccountIds:
            - "<replace by your AWS account ID>"
          Regions:
            - eu-west-1
            - us-east-1
        Variables:
          SSMParameterValue: "new-${CURRENT_ACCOUNT_ID}-${CURRENT_REGION}"
```

* Run the following command: `aws-orga-deployer apply`
* Check that the stacks were updated and the value of the parameters changed.

## Step 8: Destroy the module deployments

* Update the file `package.yaml` by:

```yaml
PackageConfiguration:
  S3Bucket: "<replace by your bucket name>"
  S3Region: "<replace by your bucket region>"
  AssumeOrgaRoleArn: "<replace by the ARN of the IAM role>"

Modules:
  ssm-parameter:
    Configuration:
      StackName: test-orga-deployer
      TemplateFilename: template.yaml
    Deployments: []
```

* Run the following command: `aws-orga-deployer apply`
* Check that the stacks and the parameters were deleted.
