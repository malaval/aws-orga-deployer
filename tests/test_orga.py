"""Test the module `aws_orga_deployer.orga`."""

# COMPLETED
import unittest

from moto import mock_organizations, mock_s3, mock_sts

from aws_orga_deployer.orga import OrgaParser
from tests import mock
from tests.mock import mock_others


class TestOrgaParser(unittest.TestCase):
    """Test the class OrgaParser."""

    @mock_sts
    @mock_others
    def setUp(self):
        """Create mock resources and an OrgaParser object that must exist for
        all tests.
        """
        # Mock CLI arguments and package configuration settings
        mock.mock_cli_arguments(package_filename="package1.yaml")
        mock.mock_package_config()
        # Enable mocking for S3 and Organizations in all tests without having
        # to add declarators to each test function
        self.mock_s3 = mock_s3()
        self.mock_s3.start()
        self.mock_organizations = mock_organizations()
        self.mock_organizations.start()
        # Create a fake S3 bucket to store the organisation cache
        mock.create_fake_bucket()
        # Create a fake AWS organization
        self.fake_orga = mock.FakeOrgaParser()
        # Create an OrgaParser object that queries the fake organization
        self.orga = OrgaParser()

    def tearDown(self):
        """Disable mocking for S3 and Organizations."""
        self.mock_s3.stop()
        self.mock_organizations.stop()

    @mock_sts
    @mock_others
    def test_reload(self):
        """Check that creating an OrgaParser works with existing cache."""
        orga = OrgaParser()
        self.assertTrue(orga.loaded_from_cache)

    def test_fetch_accounts(self):
        """Check that the value of the internal attribute `accounts` which
        stores the list of accounts is correct.
        """
        self.assertDictEqual(
            self.orga.accounts,
            {
                "123456789012": {  # Default account ID in moto
                    "Name": "master",  # Default account ID in moto
                    "ParentOUs": [self.fake_orga.root_id],
                    "Tags": {},
                    "EnabledRegions": mock.ENABLED_REGIONS,
                },
                self.fake_orga.account_a_id: {
                    "Name": "account-a-override",
                    "ParentOUs": [self.fake_orga.root_id],
                    "Tags": {"Name": "account-a-override", "Environment": "prod"},
                    "EnabledRegions": mock.ENABLED_REGIONS,
                },
                self.fake_orga.account_b_id: {
                    "Name": "account-b",
                    "ParentOUs": [self.fake_orga.ou_prod_id, self.fake_orga.root_id],
                    "Tags": {"Environment": "prod"},
                    "EnabledRegions": mock.ENABLED_REGIONS,
                },
                self.fake_orga.account_c_id: {
                    "Name": "account-c",
                    "ParentOUs": [self.fake_orga.ou_test_id, self.fake_orga.root_id],
                    "Tags": {"Environment": "test"},
                    "EnabledRegions": mock.ENABLED_REGIONS,
                },
            },
        )

    def test_fetch_ous(self):
        """Check that the value of the internal attribute `_ous` is correct."""
        self.assertDictEqual(
            self.orga.ous,
            {
                self.fake_orga.root_id: {"Tags": {}, "Name": "root"},
                self.fake_orga.ou_prod_id: {
                    "Tags": {"Environment": "prod"},
                    "Name": "prod",
                },
                self.fake_orga.ou_test_id: {
                    "Tags": {"Environment": "test"},
                    "Name": "test",
                },
            },
        )

    def test_get_all_accounts(self):
        """Check that `test_get_all_accounts` returns all accounts."""
        self.assertCountEqual(
            self.orga.get_all_accounts(),
            [
                "123456789012",
                self.fake_orga.account_a_id,
                self.fake_orga.account_b_id,
                self.fake_orga.account_c_id,
            ],
        )

    def test_get_accounts_by_id(self):
        """Check that `get_accounts_by_id` returns only account IDs that exist."""
        self.assertCountEqual(
            self.orga.get_accounts_by_id(
                [
                    self.fake_orga.account_a_id,
                    self.fake_orga.account_b_id,
                    "098765432109",
                ],  # Fake account ID
            ),
            [
                self.fake_orga.account_a_id,
                self.fake_orga.account_b_id,
            ],
        )

    def test_get_accounts_by_name(self):
        """Check that `get_accounts_by_name(["*-override"])` only returns the
        ID of account A.
        """
        self.assertCountEqual(
            self.orga.get_accounts_by_name(["*-override"]),
            [self.fake_orga.account_a_id],
        )

    def test_get_accounts_by_ou(self):
        """Check that `get_accounts_by_ou([root_id])` returns the ID of all
        accounts in the organization.
        """
        self.assertCountEqual(
            self.orga.get_accounts_by_ou([self.fake_orga.root_id]), self.orga.accounts
        )

    def test_get_accounts_by_tag(self):
        """Check that `get_accounts_by_tag(["Environment=prod"])` returns both
        accounts that have this tag.
        """
        self.assertCountEqual(
            self.orga.get_accounts_by_tag(["Environment=prod"]),
            [
                self.fake_orga.account_a_id,
                self.fake_orga.account_b_id,
            ],
        )

    def test_get_accounts_by_ou_tag(self):
        """Check that `get_accounts_by_ou(["Environment=test"])` returns only
        the account C.
        """
        self.assertCountEqual(
            self.orga.get_accounts_by_ou_tag(["Environment=test"]),
            [self.fake_orga.account_c_id],
        )

    def test_get_account_regions_1(self):
        """Check that `get_account_regions(account_id, [`ALL_ENABLED])` returns
        all enabled regions for an account.
        """
        self.assertCountEqual(
            self.orga.get_account_regions(self.fake_orga.account_a_id, ["ALL_ENABLED"]),
            mock.ENABLED_REGIONS,
        )

    def test_get_account_regions_2(self):
        """Check that `get_account_regions(account_id, REGIONS)` returns only
        the regions that intersect with the enabled regions.
        """
        self.assertCountEqual(
            self.orga.get_account_regions(
                self.fake_orga.account_a_id,
                ["us-east-1", "eu-west-1", "eu-west-3"],
            ),
            ["us-east-1", "eu-west-1"],
        )

    def test_get_all_enabled_regions(self):
        """Check that `get_all_enabled_regions()` returns all enabled regions."""
        self.assertCountEqual(
            self.orga.get_all_enabled_regions(),
            mock.ENABLED_REGIONS,
        )

    def test_get_account_name(self):
        """Check that get_account_name returns the expected account name."""
        self.assertEqual(
            self.orga.get_account_name(self.fake_orga.account_a_id),
            "account-a-override",
        )

    def test_get_account_name_invalid(self):
        """Check that get_account_name returns "undefined" if the account ID
        does not exist.
        """
        self.assertEqual(
            self.orga.get_account_name("098765432109"),
            "undefined",
        )

    def test_account_region_exists(self):
        """Check that account_region_exists returns True given that the account
        exists and the region is enabled in this account.
        """
        self.assertTrue(self.orga.account_region_exists("123456789012", "us-east-1"))

    def test_account_region_not_exists(self):
        """Check that account_region_exists returns False given that the account
        exists and the region is not enabled in this account.
        """
        self.assertFalse(self.orga.account_region_exists("123456789012", "eu-west-3"))
