---
layout: default
title: Dependencies
parent: Usage
nav_order: 3
---

# Dependencies

You can specify dependencies between module deployments in the package definition file using the attribute `Dependencies` and `VariablesFromOutputs`.

In the example below, fo each account, `module2` is deployed in all regions after `module1` has been deployed in the region `us-east-1` in the same account.

```yaml
Modules:
  module2:
    Deployments:
      - Dependencies:
          - Module: module1
            AccountId: "${CURRENT_ACCOUNT_ID}"
            Region: us-east-1
```

{: .note }
> For your information, AWS Orga Deployer uses internally the package `networkx` to build a DAG (directed acyclic graph). The nodes are the module deployments, and the edges are the dependencies.

Here are the error messages that you may obtain because of dependencies:

### `[ToModule,ToAccountId,ToRegion] depends on [FromModule,FromAccountId,FromRegion] which does not exist`

The deployment of the module `ToModule` in the account `ToAccountId` and region `ToRegion` is dependent on the deployment of `FromModule` in the account `FromAccountId` and region `FromRegion`. However, the latter deployment does not exist in the package definition file. You can ignore this type of error by using the attribute `IgnoreIfNotExists` in the package definition file.

### `The package contains circular dependencies`

Your package definition file has dependencies that are impossible to resolve.

### `[ToModule,ToAccountId,ToRegion] must be created after [FromModule,FromAccountId,FromRegion] which will be deleted during this run`

The deployment of the module `ToModule` in the account `ToAccountId` and region `ToRegion` is depend on the deployment of `FromModule` in the account `FromAccountId` and region `FromRegion`. You are trying to deploy the module `ToModule` in the account `ToAccountId` and region `ToRegion` before deplying the module `FromModule` in the account `FromAccountId` and region `FromRegion`.

### `[ToModule,ToAccountId,ToRegion] must be created after [FromModule,FromAccountId,FromRegion] which has not yet been created and will not be created during this run`

The deployment of the module `ToModule` in the account `ToAccountId` and region `ToRegion` is depend on the deployment of `FromModule` in the account `FromAccountId` and region `FromRegion`. You are trying to deploy the module `ToModule` in the account `ToAccountId` and region `ToRegion` but the deployment of the module `FromModule` in the account `FromAccountId` and region `FromRegion` will also be deleted. Therefore, the dependency will not be met anymore.

### `[FromModule,FromAccountId,FromRegion] must be deleted after [ToModule,ToAccountId,ToRegion] which has not yet been deleted and will not be deleted during this run`

The deployment of the module `ToModule` in the account `ToAccountId` and region `ToRegion` is depend on the deployment of `FromModule` in the account `FromAccountId` and region `FromRegion`. You are trying to delete the deployment of the module `FromModule` in the account `FromAccountId` and region `FromRegion` but the deployment of the module `ToModule` in the account `ToAccountId` and region `ToRegion` will will still exist. Therefore, the dependency will not be met anymore.

### `Unable to preview changes as this deployment is dependent on other deployments with pending changes`

When executing the command `preview`, the deployments that depend on other deployments cannot be evaluated if these dependencies have pending changes. For example, if a resource changes in the dependencies, this might impact the dependent deployment but we are unable to evaluate it. Therefore, these dependent deployments fail. A workaround consist of applying pending changes to the dependencies, then previewing changes for the dependent deployments.
