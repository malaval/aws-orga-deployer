---
layout: default
title: Terraform
parent: Modules
nav_order: 1
---

# Terraform

A Terraform module consists of Terraform templates. The deployment of a Terraform module consists of creating, updating or deleting resources by applying the template.

## How to develop a Terraform module?

* You need at least one TF file in the module directory (`<packageRootDir>/terraform/<moduleName>`).
* The module deployment variables are passed as Terraform variables.
    * The name of the variables must be the same than the variable key in the package definition file.
    * These variables must be declared in one of the TF files. You can use a dedicated file `variables.tf` for this.
* The module deployment outputs are automatically populated from the Terraform outputs.

{: .warning }
> The AWS provider and the state backend must **not** be declared in these files.
>
> The state backend is automatically configured by AWS Orga Deployer to store the Terraform state in the S3 bucket at `terraform/<ModuleName>/<AccountId>/<Region>/terraform.tfstate`. You must not change the state backend configuration.
>
> The AWS provider is automatically declared by AWS Orga Deployer. However, if you want to change certain attributes (e.g. fix the provider version or define default tags), you can create a file `override.tf` in the module directory that contains the attributes to override. Example:
>
> ```hcl
> provider "aws" {
>   version = "4.5.0"
>   default_tags {
>     tags = {
>       TagKey = "TagValue"
>     }
>   }
> }

### Example

In this example, there are two modules: `module1` is a Terraform module that creates a SSM parameter and return its ARN. `module2` is another module (the module files are not shown below) that refers to the outputs of `module1`.

File structure:

```text
<package>/
    package.yaml
    terraform/
        module1/
            ssm-parameter.tf
            variables.tf
```

Section of `package.yaml` that describes the module deployments:

```yaml
Modules:
    module1:
        Variables:
            parameter_value: my_value
    module2:
        VariablesFromOutputs:
            VarKey:
                Module: module1
                AccountId: "${CURRENT_ACCOUNT_ID}"
                Region: "${CURRENT_REGION}"
                OutputName: "parameter_arn"
```

Content of `ssm-parameter.tf`:

```hcl
resource "aws_ssm_parameter" "test" {
  name  = "test"
  type  = "String"
  value = var.parameter_value
}

output "parameter_arn" {
  value = aws_ssm_parameter.test.arn
}
```

Content of `variables.tf`:

```hcl
variable "parameter_value" {
  type = string
}
```

## How does it work?

AWS Orga Deployer:

* Copies the content of the module directory (the TF files) to the deployment cache directory, unless the action is `destroy` (no resources expected).
* Creates two additional files in the deployment cache directory:
    * `terraform.tfvars.json`: List of input variables and their value.
    * `aws_orga_deployer.tf`: Defines the AWS provider and the backend to stores the state in the S3 bucket. If a role must be assumed, a section `assume_role` is added to the provider.
* Runs `terraform init` in a subprocess. The plugins are downloaded in the engine cache directory.
* Runs `terraform plan -out=tfplan` in a subprocess to evaluate the changes to be made.
* Runs `terraform show -json tfplan` to display the plan in a readable format.
* If the command is `apply`:
    * Runs `terraform apply tfplan` in a subprocess
    * If the action is not `destroy`: Runs `terraform output -json` in a subprocess to read the outputs.
* Saves the result.
