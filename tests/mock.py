"""Use moto to mock boto3 resources for testing."""
# COMPLETED
from os import path
from unittest.mock import patch

import boto3
import botocore
from moto import mock_organizations, mock_s3, mock_sts

from aws_orga_deployer import config

# List of regions that we consider as enabled in mocked AWS accounts
ENABLED_REGIONS = ["us-east-1", "eu-west-1", "us-east-2"]


# Original botocore _make_api_call function
ORIG_API_CALL = botocore.client.BaseClient._make_api_call  # pylint: disable=W0212


def patch_others(self, operation_name, kwarg):
    """
    Patch operations that are not yet supported by moto:
    - account:ListRegions returns a static list of regions that are enabled in
      in an AWS account.
    """
    if operation_name == "ListRegions":
        return {"Regions": [{"RegionName": region} for region in ENABLED_REGIONS]}
    # Return the original function for other operations
    return ORIG_API_CALL(self, operation_name, kwarg)


# Function to use as a decorator to patch other operations
mock_others = patch("botocore.client.BaseClient._make_api_call", new=patch_others)


def get_test_dir():
    """Return the path of the folder containing test data.

    Returns:
        str
    """
    return path.join(path.dirname(path.abspath(__file__)), "test_data")


def get_test_path(itempath):
    """Return the full path of an item in the folder containing test data.

    Returns:
        str
    """
    return path.join(get_test_dir(), itempath)


@mock_organizations
@mock_sts
@mock_others
class FakeOrgaParser:
    """Create fake resources in AWS Organizations.

    Attributes:
        root_id (str): ID of the root resource
        ou_prod_id (str): ID of the "prod" OU whose parent is root
        ou_test_id (str): ID of the "test" OU whose parent is root
        account_a_id (str): ID of the account A whose parent is root
        account_b_id (str): ID of the account B whose parent is prod OU
        account_c_id (str): ID of the account C whose parent is test OU
        expected_accounts (dict): Expected value of the attribute accounts
        expected_ous (dict): Expected value of the attribute ous
    """

    def __init__(self):
        client = boto3.client("organizations")
        # Create an organization
        client.create_organization()
        self.root_id = client.list_roots()["Roots"][0]["Id"]
        # Create an OU "prod"
        self.ou_prod_id = client.create_organizational_unit(
            ParentId=self.root_id,
            Name="prod",
            Tags=[
                {"Key": "Environment", "Value": "prod"},
            ],
        )["OrganizationalUnit"]["Id"]
        # Create an OU "test"
        self.ou_test_id = client.create_organizational_unit(
            ParentId=self.root_id,
            Name="test",
            Tags=[
                {"Key": "Environment", "Value": "test"},
            ],
        )["OrganizationalUnit"]["Id"]
        # Create an AWS account "account-a" in the root
        self.account_a_id = client.create_account(
            Email="account-a@example.com",
            AccountName="account-a",
            Tags=[
                {"Key": "Name", "Value": "account-a-override"},
                {"Key": "Environment", "Value": "prod"},
            ],
        )["CreateAccountStatus"]["AccountId"]
        # Create an AWS account "account-b" in the OU prod
        self.account_b_id = client.create_account(
            Email="account-b@example.com",
            AccountName="account-b",
            Tags=[
                {"Key": "Environment", "Value": "prod"},
            ],
        )["CreateAccountStatus"]["AccountId"]
        client.move_account(
            AccountId=self.account_b_id,
            SourceParentId=self.root_id,
            DestinationParentId=self.ou_prod_id,
        )
        # Create an AWS account "account-c" in the OU test
        self.account_c_id = client.create_account(
            Email="account-c@example.com",
            AccountName="account-c",
            Tags=[
                {"Key": "Environment", "Value": "test"},
            ],
        )["CreateAccountStatus"]["AccountId"]
        client.move_account(
            AccountId=self.account_c_id,
            SourceParentId=self.root_id,
            DestinationParentId=self.ou_test_id,
        )


@mock_s3
def create_fake_bucket():
    """Create fake resources in Amazon S3."""
    client = boto3.client("s3", region_name="eu-west-1")
    # Create a bucket
    client.create_bucket(
        Bucket="fake-bucket",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )


def create_fake_resources():
    """Create all fake resources (S3 bucket and AWS organization)."""
    FakeOrgaParser()
    create_fake_bucket()


def mock_cli_arguments(package_filename):
    """Configure fake CLI arguments.

    Args:
        package_filename (str): Test package definition file to use.
    """
    config.CLI = {
        "package_file": path.join(get_test_dir(), package_filename),
        "command": "apply",
        "force_update": False,
        "debug": False,
    }


def mock_package_config():
    """Configure fake package settings."""
    config.PACKAGE = {
        "OverrideAccountNameByTag": "Name",
        "S3Bucket": "fake-bucket",
        "S3Region": "eu-west-1",
    }
