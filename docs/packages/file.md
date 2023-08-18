---
layout: default
title: Package definition file
parent: Packages
nav_order: 1
---

# Package definition file

* [Reference](#reference)
  * [Module configuration](#module-configuration)
  * [Module variables](#module-variables)
* [Example](#example)

## Reference

```yaml
PackageConfiguration:
  S3Bucket: string
  S3Region: string
  S3Prefix: string
  OrgaCacheExpiration: integer
  ConcurrentWorkers: integer
  AssumeOrgaRoleArn: null or string
  OverrideAccountNameByTag: string

DefaultModuleConfiguration:
  All:
    <ConfigKey>: <ConfigValue>
  terraform:
    <ConfigKey>: <ConfigValue>
  cloudformation:
    <ConfigKey>: <ConfigValue>
  python:
    <ConfigKey>: <ConfigValue>

DefaultVariables:
  All:
    <VarKey>: <VarValue>
  terraform:
    <VarKey>: <VarValue>
  cloudformation:
    <VarKey>: <VarValue>
  python:
    <VarKey>: <VarValue>

Modules:
  <moduleName>:
    Configuration:
      <ConfigKey>: <ConfigValue>
    Variables:
      <VarKey>: <VarValue>
    Deployments:
      - Include:
          AccountIds:
            - string
          AccountNames:
            - string
          AccountTags:
            - string (TAG_KEY=TAG_VALUE)
          OUIds:
            - string
          OUTags:
            - string (TAG_KEY=TAG_VALUE)
          Regions:
            - string
        Exclude:
          AccountIds:
            - string
          AccountNames:
            - string
          AccountTags:
            - string (TAG_KEY=TAG_VALUE)
          OUIds:
            - string
          OUTags:
            - string (TAG_KEY=TAG_VALUE)
          Regions:
            - string
        Dependencies:
          - Module: string
            AccountId: string
            Region: string
        Variables:
          <VarKey>: <VarValue>
        VariablesFromOutputs:
          <VarKey>:
            Module: string
            AccountId: string
            Region: string
            OutputName: output
```

* `PackageConfiguration` **[REQUIRED]**:
  * `S3Bucket` **[REQUIRED]**: Name of the S3 bucket used to store package persistent data (cached information about AWS accounts and organizational units, package state, Terraform states, etc.).
  * `S3Region` **[REQUIRED]**: AWS region where this S3 bucket resides (e.g. `eu-west-1`).
  * `S3Prefix`: Key prefix used when writing objects in the bucket. It must end with a `/`. If no value is provided, objects are written at the root of the S3 bucket.
  * `OrgaCacheExpiration`: AWS Orga Deployer stores information about AWS accounts and organizational units obtained from AWS Organizations in the S3 bucket at `s3://<S3Bucket>/<S3Prefix>/orga.json`. AWS Orga Deployer reuses the cache in S3 instead of querying AWS Organizations if the cache was generated less than `OrgaCacheExpiration` seconds ago. The default value is 300 (5 minutes).
  * `ConcurrentWorkers`: Number of concurrent threads that AWS Orga Deployer uses to create, update or destroy module deployments. The default value is `10`.
  * `AssumeOrgaRoleArn`: ARN of the IAM role that AWS Orga Deployer must assume before querying AWS Organizations. By default, AWS Orga Deployer doesn't assume an IAM role and uses the current credentials instead.
  * `OverrideAccountNameByTag`: To replace account names fetched from AWS Organizations by the value of a specific tag assigned to AWS accounts, provide the key of that tag. If that tag is not assigned to an AWS account, the account name remains unchanged.
* `DefaultModuleConfiguration`: See [Module configuration](#module-configuration).
* `DefaultVariables`: See [Module variables](#module-variables)
* `Modules` **[REQUIRED]**: List of modules to deploy. For each module:
  * `<moduleName>` **[REQUIRED]**: Name of the module, defined by the name of the folder that contains module files. For example, the files of the Python module `python1` must be located in the folder `python/python1`.
    * `Configuration`: See [Module configuration](#module-configuration).
    * `Variables`: See [Module variables](#module-variables).
    * `VariablesFromOutputs`: List of variables that are valued by the outputs of other deployments.
      * `<VarKey>`: Name of the variable.
        * `Module` **[REQUIRED]**: Name of the module for the dependent deployment.
        * `AccountId` **[REQUIRED]**: AWS account ID for the dependent deployment.
        * `Region` **[REQUIRED]**: Region for the dependent deployment.
        * `OutputName` **[REQUIRED]**: Name of the output in the dependent deployment.
    * `Deployments` **[REQUIRED]**: List of deployment blocks for this module. Each deployment block specifies a scope of AWS accounts and regions where the module must be deployed with a specific configuration:
      * `Include`: AWS accounts and regions included in the scope of deployments. If `Include` is not specified, the module is deployed in all enabled regions of all AWS accounts in the organization, except the scope eventually specified by `Exclude`.
        * `AccountIds`: List of AWS accounts IDs to include.
        * `AccountNames`: List of account names to include (case sensitive). You can use the wildcard character `*` (e.g. `*-prod`).
        * `AccountTags`: List of `TAG_KEY=TAG_VALUE` (case sensitive). Only the AWS accounts with these tags assigned are included.
        * `OUIds`: List of organizational unit IDs. Only the AWS accounts that are directly or indirectly in one of these OUs are included.
        * `OUTags`: List of `TAG_KEY=TAG_VALUE` (case sensitive). Only the AWS accounts that are directly or indirectly in one of the OUs with these tags assigned are included.
        * `Regions`: List of regions to include. By default, all enabled regions are included.
      * `Exclude`: AWS accounts and regions excluded from the scope of deployments. If `Exclude` is not specified, no deployments are excluded and the module is deployed in the accounts and regions specified by `Include`.
        * `AccountIds`: List of AWS accounts IDs to include.
        * `AccountNames`: List of account names to include (case sensitive). You can use the wildcard character `*` (e.g. `*-prod`).
        * `AccountTags`: List of `TAG_KEY=TAG_VALUE` (case sensitive). Only the AWS accounts with these tags assigned are included.
        * `OUIds`: List of organizational unit IDs. Only the AWS accounts that are directly or indirectly in one of these OUs are included.
        * `OUTags`: List of `TAG_KEY=TAG_VALUE` (case sensitive). Only the AWS accounts that are directly or indirectly in one of the OUs with these tags assigned are included.
        * `Regions`: List of regions to exclude.
      * `Variables`: See [Module variables](#module-variables).
      * `Dependencies`: List of deployments that must be created before these deployments, and deleted after these deployments.
        * `Module` **[REQUIRED]**: Name of the module for the dependent deployment.
        * `AccountId` **[REQUIRED]**: AWS account ID for the dependent deployment.
        * `Region` **[REQUIRED]**: Region for the dependent deployment.
      * `VariablesFromOutputs`: Same as above but apply to the deployment block only.

{: .note-title }
> Note 1
>
> You can use the expressions `${CURRENT_ACCOUNT_ID}` and `${CURRENT_REGION}` in the value of any variables, dependencies or module configuration attribute. The expressions are replaced respectively by the AWS account ID and the region of the current deployment.
>
> In the example below, `${CURRENT_ACCOUNT_ID}` is replaced by the ID of the AWS account in which the module is being deployed (`123456789012` or `123456789013`).
>
> ```yaml
> Modules:
>   module1:
>     Configuration:
>       AssumeRole: "arn:aws:iam::${CURRENT_ACCOUNT_ID}:role/RoleName"
>     Deployments:
>       - Include:
>           AccountIds:
>             - "123456789012"
>             - "123456789013"
> ```

{: .note-title }
> Note 2
>
> For a given module, if the same deployment is defined in multiple deployment blocks, the last declaration prevails. In the example below, the last declaration prevails for the AWS account ID `123456789012` and the variable is equal to `value2`.
>
> ```yaml
> Modules:
>   module1:
>     Variables:
>       myVar: value0
>     Deployments:
>       - Include:
>           AccountIds:
>             - "123456789012"
>             - "123456789013"
>         Variables:
>           myVar: "value1"
>       - Include:
>           AccountIds:
>             - "123456789012"
>         Variables:
>           myVar: "value2"
> ```

{: .note-title }
> Note 3
>
> You can use YAML aliases to avoid repeating yourself. The example below shows how to declare a list of AWS account IDs as an alias and how to use this alias.
>
> ```yaml
> myalias: &myalias
>   - "123456789012"
>   - "123456789013"
>   - "123456789014"
> 
> Modules:
>   module1:
>     Deployments:
>       - Include:
>           AccountIds: *myalias
>   module2:
>     Deployments:
>       - Include:
>           AccountIds: *myalias
> ```

### Module configuration

Modules require or support configuration settings that depend on the engine. The configuration settings can be defined at different levels:

* `root["defaultConfiguration"]["All"]`: Apply to all module deployments for all engines.
* `root["defaultConfiguration"]["<engineName>"]`: Apply to all module deployments for a given engine. Override the attributes defined above. 
* `root["Modules"]["<moduleName>"]["Configuration"]`: Apply to all deployments for a given module. Override the attributes defined above.

#### Attributes common to all modules

```yaml
Configuration:
  AssumeRole: null or string
  Retry:
    MaxAttempts: integer
    DelayBeforeRetrying: integer
  EndpointUrls:
    <serviceName>: endpoint
```

* `AssumeRole`: ARN of the IAM role to assume before creating resources for this deployment. By default, or if equal to `null`, AWS Orga Deployer doesn't assume an IAM role and use the current credentials instead.
* `Retry`:
  * `MaxAttempts`: Maximum number of times AWS Orga Deployer attempts to create, update or destroy the deployment. The default is `1` (no retries).
  * `DelayBeforeRetrying`: Number of seconds AWS Orga Deployer waits before retrying. This can be useful notably when you need to wait because of eventual consistency.
* `EndpointUrls`: Specify this attribute to use custom AWS endpoints. You must add one line per service. This is notably notably needed for testing with Moto.
  * `<serviceName>`: Service name (e.g. `iam`, `s3`, `sts`, etc.).
  * `endpoint`: Endpoint URL.

#### Attributes specific to Terraform modules

```yaml
Configuration:
  TerraformExecutable: string
```

* `TerraformExecutable`: Path to the Terraform executable. The default is `terraform`.

#### Attributes specific to CloudFormation modules

```yaml
Configuration:
  StackName: string
  TemplateFilename: string
  PythonExecutable: string
  AdditionalBoto3Parameters:
    <Key>: <Value>
```

* `StackName` **[REQUIRED]**: Name of the CloudFormation stack to create.
* `TemplateFilename` **[REQUIRED]**: Name of the template in the module files (e.g. `template.yaml`).
* `PythonExecutable`: Path to the Python executable to use to launch the Python script that makes calls to CloudFormation. The default is `python3`.
* `AdditionalBoto3Parameters`: Dictionary with additional parameters to pass to the `CreateChangeSet` boto3 method. For example, you can provide a value for `Tags` to tag all the resources created by CloudFormation.

#### Attributes specific to Python modules

```yaml
Configuration:
  PythonExecutable: string
```

* `PythonExecutable`: Path to the Python executable to use. The default is `python3`.

### Module variables

The variables passed to modules can be defined at different levels:

* `root["DefaultVariables"]["All"]`: Apply to all module deployments for all engines.
* `root["DefaultVariables"]["<engineName>"]`: Apply to all module deployments for a given engine. Override the variables defined above. 
* `root["Modules"]["<moduleName>"]["Variables"]`: Apply to all deployments for a given module. Override the variables defined above.
* `root["Modules"]["<moduleName>"]["Deployments"][N]["Variables"]`: Apply to the deployments of a given deployment block. Override the variables defined above.

The variables valued by the outputs of other deployments can be defined at two levels:

* `root["Modules"]["<moduleName>"]["VariablesFromOutputs"]`: Apply to all deployments for a given module. Override the variables defined above.
* `root["Modules"]["<moduleName>"]["Deployments"][N]["VariablesFromOutputs"]`: Apply to the deployments of a given deployment block. Override the variables defined above.

Notes:

* If the same variable is declared in both `Variables` and `VariablesFromOutputs`, the value of `VariablesFromOutputs` prevails.
* For CloudFormation modules, list values are transformed as strings with commas as separator. All other variable values are passed as-is.

## Example

```yaml
PackageConfiguration:
  S3Bucket: my-bucket
  S3Region: eu-west-1
  S3Prefix: package1/
  AssumeOrgaRoleArn: "arn:aws:iam::123456789012:role/OrganizationsReadOnly"
  OverrideAccountNameByTag: AccountFriendlyName

DefaultModuleConfiguration:
  All:
    AssumeRole: "arn:aws:iam::${CURRENT_ACCOUNT_ID}:role/LandingZoneDeploymentRole"

Modules:
  python1:
    Configuration:
      Retry:
        MaxAttempts: 2
        DelayBeforeRetrying: 60
    Deployments:
      - Include:
          AccountNames: ["*-prod"]
          OUIds: ["ou-12345"]
          Regions: ["us-east-1"]
        Variables:
          variable1: "value1"
  cloudformation1:
    Configuration:
    StackName: "SecurityLandingZone"
      Retry:
        MaxAttempts: 2
        DelayBeforeRetrying: 60
    Deployments:
      - Include:
          AccountNames: ["*-prod"]
          OUIds: ["ou-12345"]
        Exclude:
          AccountNames: ["excluded-prod"]
        VariablesFromOutputs:
          variable2:
            Module: python1
            AccountId: "${CURRENT_ACCOUNT_ID}"
            Region: us-east-1
            OutputName: "iamRoleArn"
```

The package persistent data is stored in the S3 bucket `my-bucket` in the region `eu-west-1` with the prefix `package1`. AWS Orga Deployer assumes the role `arn:aws:iam::123456789012:role/OrganizationsReadOnly` to query AWS Organizations. If an AWS account has the tag `AccountFriendlyName` assigned in AWS Organizations, the tag value overrides the account name.

The package deploys two modules:

* `python1`:
  * Deployed in all AWS accounts in the organizational unit `ou-12345` and whose name ends with `-prod`, only in the region `us-east-1`.
  * The variable `variable1` has a static value `value1`.
  * If a deployment fails, AWS Orga Deployer waits for 60 seconds and retries a second time.

* `cloudformation1`:
  * Deployed in all AWS accounts in the organizational unit `ou-12345` and whose name ends with `-prod` except the account `excluded-prod`, in all enabled regions of each account.
  * The variable `variable2` is valued by the output `iamRoleArn` of the deployment of `python1` in the same account in `us-east-1`.
  * The CloudFormation stack that AWS Orga Deployer creates is named `SecurityLandingZone`.
