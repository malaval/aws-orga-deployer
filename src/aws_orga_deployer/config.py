"""Constants or variables shared across multiple modules."""

# COMPLETED
from typing import Any, Dict

# CLI arguments populated by the module `cli`
CLI: Dict[str, Any] = {}

# Package configuration settings populated by the sub-package `package`
PACKAGE: Dict[str, Any] = {}

# Engine class instances for each module, populated by the module `Modules`
MODULES: Dict = {}

# Default location of the package definition YAML file
DEFAULT_PACKAGE_FILE: str = "package.yaml"

# Default location of the output JSON file
DEFAULT_OUTFILE_FILE: str = "output.json"

# Default location of the temporary directory that contains cache and logs
DEFAULT_TEMP_DIR: str = ".aws-orga-deployer"

# Number of concurrent threads used to query AWS Organizations
CONCURRENT_ORGA_THREADS: int = 10

# Name of the S3 file that stores the organization cache
ORGA_CACHE_FILENAME: str = "orga.json"

# Default period in seconds during which the organization description cached in
# S3 is reused instead of querying AWS Organizations (5 minutes)
DEFAULT_ORGA_CACHE_EXPIRATION: int = 5 * 60

# Name of the package state file in S3
STATE_FILENAME: str = "state.json"

# Name of the optional file in the module folder that contains patterns of
# filename to include or exclude to calculate module hash
HASH_CONFIG_FILENAME: str = "hash-config.json"

# Default number of concurrent workers
DEFAULT_CONCURRENT_WORKERS: int = 10

# Number of seconds during which the same AWS temporary credentials are provided
# to workers that must assume the same IAM role
CACHE_AWS_TEMP_CREDS: int = 5 * 60

# Duration of the AWS temporary credentials in seconds
AWS_TEMP_CREDS_DURATION: int = 60 * 60
