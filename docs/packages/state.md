---
layout: default
title: Package state
parent: Packages
nav_order: 2
---

# Package state

The package state is the file `state.json` stored in the S3 bucket. It is created and updated by AWS Orga Deployer, and you should not edit it manually. However, this page describes its format for reference.

```json
{
    "Deployments": [
        {
            "Deployment": {
                "Module": "string",
                "AccountId": "string",
                "Region": "string"
            },
            "CurrentState": {
                "Variables": {
                    "<VarKey>": "<VarValue>"
                },
                "VariablesFromOutputs": {
                    "<VarKey>": {
                        "Module": "string",
                        "AccountId": "string",
                        "Region": "string",
                        "OutputName": "string"
                    }
                },
                "Dependencies": [
                    {
                        "Module": "string",
                        "AccountId": "string",
                        "Region": "string"
                    }
                ],
                "ModuleHash": "string",
                "Outputs": {
                    "<OutputKey>": "<OutputValue>"
                },
                "LastChangedTime": "YYYY-MM-DD HH:MM:SS.mmmmmm"
            }
        }
    ]
}
```

* `Deployments` **[REQUIRED]**: List of existing module deployments. For each deployment:
    * `Deployment` **[REQUIRED]**:
        * `Module` **[REQUIRED]**: Name of the module deployed.
        * `AccountId` **[REQUIRED]**: AWS account ID in which the module is deployed.
        * `Region` **[REQUIRED]**: Region in which the module is deployed.
    * `CurrentState` **[REQUIRED]**:
        * `Variables` **[REQUIRED]**: Dictionary containing the variables passed to the module and their value, including the values derived from the outputs of other deployments. Can be an empty dictionary.
        * `VariablesFromOutputs` **[REQUIRED]**: Dictionary containing the variables valued from the outputs of other deployments. Can be an empty dictionary.
        * `Dependencies` **[REQUIRED]**: List of dependencies. Can be an empty list.
        * `ModuleHash` **[REQUIRED]**: Value of the module hash at the time the module was deployed.
        * `Outputs` **[REQUIRED]**: Dictionary containing the module outputs and their value. Can be an empty dictionary.
        * `LastChangedTime` **[REQUIRED]**: Last time this module was created or updated.
