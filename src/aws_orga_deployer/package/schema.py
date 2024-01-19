"""Define the schema of the package definition file."""

from typing import Dict

import jsonschema

from aws_orga_deployer import config
from aws_orga_deployer.engines import ENGINES


def validate(content: Dict) -> None:
    """Validate the content provided with the schema.

    Args:
        content: Dict to validate.

    Raise:
        ValidationError: If the schema is invalid.
    """
    schema = {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "PackageConfiguration": {
                "description": "Package configuration settings",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "S3Bucket": {
                        "description": "Name of the S3 bucket to store persistent data",
                        "type": "string",
                        "minLength": 3,
                    },
                    "S3Region": {
                        "description": "Region of the S3 bucket",
                        "type": "string",
                        "minLength": 3,
                    },
                    "S3Prefix": {
                        "description": "S3 prefix. Must ends with a slash if specified",
                        "type": "string",
                        "pattern": "^.+\\/$",
                    },
                    "ConcurrentWorkers": {
                        "description": "Number of concurrent threads deploying modules",
                        "type": "number",
                        "minimum": 1,
                        "maximum": 50,
                    },
                    "AssumeOrgaRoleArn": {
                        "description": (
                            "ARN of the IAM role to assume to query AWS Organizations"
                        ),
                        "type": "string",
                    },
                    "OrgaCacheExpiration": {
                        "description": (
                            "Period in seconds during which the cache in S3 of"
                            " information on accounts and organizational units is"
                            " reused instead of querying AWS Organizations"
                        ),
                        "type": "number",
                        "minimum": 0,
                    },
                    "OverrideAccountNameByTag": {
                        "description": (
                            "Tag key assigned to AWS accounts whose value is used to"
                            " override the account name"
                        ),
                        "type": "string",
                    },
                },
                "required": ["S3Bucket", "S3Region"],
            },
            "DefaultModuleConfiguration": {
                "description": (
                    "Default configuration settings for all modules or modules of a"
                    " given engine"
                ),
                "type": "object",
                "propertyNames": {"enum": ["All", *ENGINES]},
                "patternProperties": {"^": {"type": "object"}},
                "additionalProperties": False,
            },
            "DefaultVariables": {
                "description": (
                    "Default variables for all modules or modules of a given engine"
                ),
                "type": "object",
                "propertyNames": {"enum": ["All", *ENGINES]},
                "patternProperties": {"^": {"type": "object"}},
                "additionalProperties": False,
            },
            "Modules": {
                "description": "Module deployments definition",
                "type": "object",
                "propertyNames": {"enum": [*config.MODULES]},
                "patternProperties": {
                    "^": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "Configuration": {
                                "description": "Module configuration settings",
                                "type": "object",
                            },
                            "Variables": {
                                "description": "Module variables",
                                "type": "object",
                            },
                            "VariablesFromOutputs": {
                                "type": "object",
                                "patternProperties": {
                                    "^": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "Module": {
                                                "type": "string",
                                                "enum": [*config.MODULES],
                                            },
                                            "Region": {"type": "string"},
                                            "AccountId": {"type": "string"},
                                            "OutputName": {"type": "string"},
                                        },
                                        "required": [
                                            "Module",
                                            "Region",
                                            "AccountId",
                                            "OutputName",
                                        ],
                                    }
                                },
                            },
                            "Deployments": {
                                "description": "List of module deployments",
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "Include": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "AccountIds": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string",
                                                        "pattern": "^[0-9]{12}$",
                                                    },
                                                },
                                                "AccountNames": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                                "AccountTags": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string",
                                                        "pattern": "^.+=.+$",
                                                    },
                                                },
                                                "OUIds": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                                "OUTags": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string",
                                                        "pattern": "^.+=.+$",
                                                    },
                                                },
                                                "Regions": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                        "Exclude": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "AccountIds": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string",
                                                        "pattern": "^[0-9]{12}$",
                                                    },
                                                },
                                                "AccountNames": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                                "AccountTags": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string",
                                                        "pattern": "^.+=.+$",
                                                    },
                                                },
                                                "OUIds": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                                "OUTags": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string",
                                                        "pattern": "^.+=.+$",
                                                    },
                                                },
                                                "Regions": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                        "Variables": {"type": "object"},
                                        "VariablesFromOutputs": {
                                            "type": "object",
                                            "patternProperties": {
                                                "^": {
                                                    "type": "object",
                                                    "additionalProperties": False,
                                                    "properties": {
                                                        "Module": {
                                                            "type": "string",
                                                            "enum": [*config.MODULES],
                                                        },
                                                        "Region": {"type": "string"},
                                                        "AccountId": {"type": "string"},
                                                        "OutputName": {
                                                            "type": "string"
                                                        },
                                                        "IgnoreIfNotExists": {
                                                            "type": "boolean"
                                                        },
                                                    },
                                                    "required": [
                                                        "Module",
                                                        "Region",
                                                        "AccountId",
                                                        "OutputName",
                                                    ],
                                                }
                                            },
                                        },
                                        "Dependencies": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "Module": {
                                                        "type": "string",
                                                        "enum": [*config.MODULES],
                                                    },
                                                    "Region": {"type": "string"},
                                                    "AccountId": {"type": "string"},
                                                    "IgnoreIfNotExists": {
                                                        "type": "boolean"
                                                    },
                                                },
                                                "required": [
                                                    "Module",
                                                    "Region",
                                                    "AccountId",
                                                ],
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "required": ["Deployments"],
                    }
                },
            },
        },
        "required": ["PackageConfiguration", "Modules"],
    }
    jsonschema.validate(instance=content, schema=schema)
