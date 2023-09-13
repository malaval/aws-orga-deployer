---
layout: default
title: CloudFormation
parent: Modules
nav_order: 2
---

# CloudFormation

A CloudFormation module consists of a CloudFormation template. The deployment of a CloudFormation module consists of creating, updating or deleting a CloudFormation stack from this template.

## How to develop a CloudFormation module?

* You need at least one file YAML or JSON template file in the module directory (`<packageRootDir>/cloudformation/<moduleName>`).
* You need to specify the name of the file and the name of stack in the module configuration. See [Package definition file](../package/file.html#attributes-specific-to-cloudformation-modules)
* The module deployment variables are passed as input parameters to the stack. These input parameters must exist in the template.
* The module deployment outputs are automatically populated from the stack outputs.

### Example

In this example, there are two modules: `module1` is a CloudFormation module that creates a SSM parameter and return its ID. `module2` is another module (the module files are not shown below) that refers to the outputs of `module1`.

File structure:

```text
<package>/
    package.yaml
    cloudformation/
        module1/
            template.yaml
```

Section of `package.yaml` that describes the module deployments:

```yaml
Modules:
    module1:
        Variables:
            SSMParameterValue: my_value
    module2:
        VariablesFromOutputs:
            VarKey:
                Module: module1
                AccountId: "${CURRENT_ACCOUNT_ID}"
                Region: "${CURRENT_REGION}"
                OutputName: "SSMParameterID"
```

Content of `template.yaml`:

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
Outputs:
  SSMParameterID:
    Description: SSM Parameter ID
    Value: !Ref SSMParameter
```

## How does it work?

* AWS Orga Deployer writes deployment inputs (CLI command, deployment action, etc.) into a file named `input.json` stored in the deployment cache directory.
* AWS Orga Deployer executes a Python script - a *wrapper* - in a subprocess that:
    * Reads the inputs from the file `input.json`. This file allows the main process and the subprocess to communicate.
    * If the action is `create` or `update`:
        * Create a change set to evaluate the changes to be made (similar to `terraform plan` in Terraform).
        * If the command is `apply`: Applies the changes
        * If the command is `preview`: Deletes the change set
    * If the action is `delete`:
        * Retrieves the list of existing resources that must be deleted
        * If the command is `apply`: Deletes the stack unless it does not exist.
    * Write the outputs of the function `main` to a file `output.json` in the deployment cache directory.
* The main process reads the content of the file `output.json` and saves the result.

{: .note }
> If an IAM role is specified in `AssumeRole` for the module configuration, AWS Orga Deployer assumes that role and set the temporary credentials as environment variables of the subprocess. If no role is to be assumed, the subprocess uses the same AWS credentials than the main process.
