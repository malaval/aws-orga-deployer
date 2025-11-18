"""Information on AWS accounts and organizational units."""

# COMPLETED
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import botocore

from aws_orga_deployer import config, utils

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class OrgaParser:
    """Class to retrieve and use information from AWS Organizations.

    Attributes:
        accounts: Information about accounts
        ous: Information about organizational units
        loaded_from_cache: True if it was loaded from the cache in S3
    """

    accounts: Dict[str, Any]
    ous: Dict[str, Any]
    loaded_from_cache: bool

    def __init__(self) -> None:
        """Load and parse information on AWS accounts and OUs."""
        # If the information on accounts and organizational units could not be
        # loaded from the cache in S3, query AWS Organizations
        self.loaded_from_cache = self._load_from_cache()
        if self.loaded_from_cache is False:
            LOGGER.info(
                "Querying AWS Organizations for information on accounts and"
                " organizational units"
            )
            # Create a session with permissions to query AWS Organizations
            self.master_session = utils.get_aws_session(
                config.PACKAGE.get("AssumeOrgaRoleArn")
            )
            # Query AWS Organizations
            self._fetch_accounts()
            self._fetch_ous()
            # Update the cache in S3
            content = self.export()
            utils.write_dict_to_s3(content, config.ORGA_CACHE_FILENAME)
        LOGGER.info(
            "Found %s accounts and %s organizational units",
            len(self.accounts),
            len(self.ous),
        )

    def _load_from_cache(self) -> bool:
        """Load information on accounts and organizational units from the cache
        in S3 if it exists and has not expired, and if the CLI argument
        `--force-orga-refresh` is not passed.

        Returns:
            True if the cache in S3 was used to load information about accounts
                and organizational units, False otherwise.
        """
        # If the argument --force-orga-refresh is passed, return False
        if config.CLI.get("force_orga_refresh", False):
            LOGGER.debug(
                "Ignoring the cache in S3 and forcing the tool to query AWS"
                " Organizations"
            )
            return False
        client = utils.get_aws_client(
            utils.get_aws_session(), "s3", region_name=config.PACKAGE["S3Region"]
        )
        bucket = config.PACKAGE["S3Bucket"]
        key = utils.get_s3_key(config.ORGA_CACHE_FILENAME)
        # Returns the number of seconds since the cache in S3 was modified for
        # the last time
        try:
            LOGGER.debug(
                "Retrieving the last modification date of the cache of information"
                " on accounts and organizational units at s3://%s/%s",
                bucket,
                key,
            )
            response = client.head_object(Bucket=bucket, Key=key)
            modified_date = response["LastModified"].replace(tzinfo=None)
            seconds = (datetime.utcnow() - modified_date).total_seconds()
            expiration = config.PACKAGE.get(
                "OrgaCacheExpiration",
                config.DEFAULT_ORGA_CACHE_EXPIRATION,
            )
            # Load information from the cache if it has not expired
            if seconds <= expiration:
                LOGGER.info(
                    "Loading information on accounts and organizational units from the"
                    " cache in S3"
                )
                cache = utils.load_json_from_s3(config.ORGA_CACHE_FILENAME)
                self.accounts = cache["Accounts"]
                self.ous = cache["OUs"]
                return True
            # If the cache has expired
            LOGGER.debug(
                "The cache in S3 of information on accounts and organizational units"
                " has expired"
            )
            return False
        # Return False if there is no cache in S3 or if the cache could not be
        # loaded
        except botocore.exceptions.ClientError as err:
            if (
                isinstance(err, botocore.exceptions.ClientError)
                and err.response["Error"]["Message"] == "Not Found"
            ):
                LOGGER.debug(
                    "There is no cache of information on accounts and organizational"
                    " units in S3"
                )
            else:
                LOGGER.exception(
                    "Failed to load the cache of information on accounts and"
                    " organizational units from S3",
                    exc_info=config.CLI["debug"],
                )
            return False

    def _fetch_accounts(self) -> None:
        """
        Query AWS Organizations for information on AWS accounts and store it in
        the attribute `accounts`.
        """
        orga_client = utils.get_aws_client(self.master_session, "organizations")
        account_client = utils.get_aws_client(self.master_session, "account")
        sts_client = utils.get_aws_client(self.master_session, "sts")
        master_account_id = sts_client.get_caller_identity()["Account"]
        accounts: Dict[str, Dict] = {}

        def browse_ou(ou_id: str, parent_ou_ids: Optional[List[str]] = None) -> None:
            """Retrieve the children of an OU and process recurvisely the
            child OUs.

            Args:
                ou_id: ID of the organizational unit to process.
                parent_ou_ids: List of parent OU IDs. Default corresponds to an
                    empty list.
            """
            ou_ids = [ou_id]
            if not parent_ou_ids is None:
                ou_ids += parent_ou_ids
            # Append the list of parent OUs of each account in this OU
            children_accounts = orga_client.list_children(
                ParentId=ou_id, ChildType="ACCOUNT"
            )["Children"]
            for children_account in children_accounts:
                if children_account["Id"] in accounts:
                    accounts[children_account["Id"]]["ParentOUs"] = ou_ids
            # Browse recursively the organization
            children_ous = orga_client.list_children(
                ParentId=ou_id, ChildType="ORGANIZATIONAL_UNIT"
            )["Children"]
            for children_ou in children_ous:
                browse_ou(children_ou["Id"], ou_ids)

        def get_account_tags_regions(account_id: str) -> None:
            """Retrieve the tags and enabled regions of an account. Update the
            account name if it must be replaced by the value of a given tag if
            it exists.

            Args:
                account_id: ID of the account.
            """
            accounts[account_id]["Tags"] = {}
            # Retrieve the tags
            paginator = orga_client.get_paginator("list_tags_for_resource")
            pages = paginator.paginate(ResourceId=account_id)
            for page in pages:
                for tag in page["Tags"]:
                    accounts[account_id]["Tags"][tag["Key"]] = tag["Value"]
            # Update the account name if needed
            tag_key = config.PACKAGE.get("OverrideAccountNameByTag")
            if tag_key in accounts[account_id]["Tags"]:
                new_account_name = accounts[account_id]["Tags"][tag_key]
                accounts[account_id]["Name"] = new_account_name
            # Retrieve the enabled regions. The argument `AcountId` must not
            # be passed to the `list_regions` request for the master account
            if account_id == master_account_id:
                regions = account_client.list_regions(
                    RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
                )["Regions"]
            else:
                regions = account_client.list_regions(
                    AccountId=account_id,
                    RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"],
                )["Regions"]
            enabled_regions = [region["RegionName"] for region in regions]
            accounts[account_id]["EnabledRegions"] = enabled_regions

        # List the accounts that exist in the organization in a dict with
        # {account_id: {'Name': account_name}}. Exclude non-active accounts.
        paginator = orga_client.get_paginator("list_accounts")
        pages = paginator.paginate()
        for page in pages:
            for account in page["Accounts"]:
                # Attribute "Status" is getting deprecated in 2025-26
                if (
                    account.get("Status") == "ACTIVE"
                    or account.get("State") == "ACTIVE"
                ):
                    accounts[account["Id"]] = {"Name": account["Name"]}

        # Recursively browse the organization to find the parent OUs for each
        # account
        roots = orga_client.list_roots()["Roots"]
        for root in roots:
            browse_ou(root["Id"])

        # Retrieve the account tags and enabled the regions for each account
        # using concurrent threads
        utils.exec_multithread(
            list(accounts.keys()),
            get_account_tags_regions,
            config.CONCURRENT_ORGA_THREADS,
        )
        self.accounts = accounts

    def _fetch_ous(self) -> None:
        """
        Query AWS Organizations for information on organizational units and
        store it in the attribute `_ous`.
        """
        orga_client = utils.get_aws_client(self.master_session, "organizations")
        ous: Dict[str, Dict] = {}

        # Get the list of unique OUs
        ou_ids = []
        for account in self.accounts.values():
            ou_ids += account["ParentOUs"]
        ou_ids = list(set(ou_ids))

        def get_ou_name_tags(ou_id: str) -> None:
            """Retrieve the name and the tags of an organizational unit.

            Args:
                ou_id (str): ID of the OU
            """
            ous[ou_id] = {}
            ous[ou_id]["Tags"] = {}
            # Retrieve the name
            if ou_id.startswith("ou-"):
                ous[ou_id]["Name"] = orga_client.describe_organizational_unit(
                    OrganizationalUnitId=ou_id
                )["OrganizationalUnit"]["Name"]
            else:
                ous[ou_id]["Name"] = "root"
            # Retrieve the tags
            paginator = orga_client.get_paginator("list_tags_for_resource")
            pages = paginator.paginate(ResourceId=ou_id)
            for page in pages:
                for tag in page["Tags"]:
                    ous[ou_id]["Tags"][tag["Key"]] = tag["Value"]

        # Retrieve the name and the tags for each OU using concurrent threads
        utils.exec_multithread(ou_ids, get_ou_name_tags, config.CONCURRENT_ORGA_THREADS)
        self.ous = ous

    def export(self) -> Dict[str, Dict[str, Dict]]:
        """Returns a dict with information on AWS accounts and organizational
        units.

        Returns:
            Dictionary whose structure is::

                {
                    'Accounts': accounts,
                    'OUs: ous
                }

        """
        return {"Accounts": self.accounts, "OUs": self.ous}

    def get_all_accounts(self) -> List[str]:
        """Return the list of all accounts IDs in the organization.

        Returns:
            List of account IDs.
        """
        return [*self.accounts]

    def get_accounts_by_id(self, account_ids: List[str]) -> List[str]:
        """Return the list of accounts IDs in the organization that intersect
        with a given list of account IDs.

        Args:
            account_ids: List of account IDs.

        Returns:
            List of account IDs.
        """
        return [account_id for account_id in self.accounts if account_id in account_ids]

    def get_accounts_by_name(self, patterns: List[str]) -> List[str]:
        """Return the list of accounts IDs in the organization whose account
        name matches one of the given patterns.

        Args:
            patterns: List of account name patterns.

        Returns:
            List of account IDs.
        """

        result = []
        for account_id, account in self.accounts.items():
            for pattern in patterns:
                expr = re.escape(pattern).replace("\\*", ".*")
                expr = "^" + expr + "$"
                if re.match(expr, account["Name"]):
                    result.append(account_id)
                    break
        return result

    def get_accounts_by_ou(self, ou_ids: List[str]) -> List[str]:
        """Return the list of account IDs in the organization that belong to
        at least one of the organization units in a given list.

        Args:
            out_ids: List of organizational unit IDs.

        Returns:
            List of account IDs.
        """
        result = []
        for account_id, account in self.accounts.items():
            for parent_ou in account["ParentOUs"]:
                if parent_ou in ou_ids:
                    result.append(account_id)
                    break
        return result

    def get_accounts_by_tag(self, tags: List[str]) -> List[str]:
        """Return the list of account IDs in the organization that have a set of
        given tags assigned.

        Args:
            tags: List of tags TAG_KEY=TAG_VALUE.

        Returns:
            List of account IDs.
        """
        result = []
        for account_id, account in self.accounts.items():
            account_has_all_tags = True
            for tag in tags:
                tag_key, tag_value = tag.split("=")
                if not account["Tags"].get(tag_key) == tag_value:
                    account_has_all_tags = False
                    break
            if account_has_all_tags:
                result.append(account_id)
        return result

    def get_accounts_by_ou_tag(self, tags: List[str]) -> List[str]:
        """Return the list of account IDs in the organization that belong to
        at least one organizational unit that have a set of given tags assigned.

        Args:
            tags: List of tags TAG_KEY=TAG_VALUE.

        Returns:
            List of account IDs.
        """
        result = []
        for account_id, account in self.accounts.items():
            for parent_ou_id in account["ParentOUs"]:
                ou_has_all_tags = True
                parent_ou_tags = self.ous[parent_ou_id]["Tags"]
                for tag in tags:
                    tag_key, tag_value = tag.split("=")
                    if not parent_ou_tags.get(tag_key) == tag_value:
                        ou_has_all_tags = False
                        break
                if ou_has_all_tags:
                    result.append(account_id)
                    break
        return result

    def get_account_regions(self, account_id: str, regions: List[str]) -> List[str]:
        """Return the list of regions that are enabled in a given account and
        that intersect with a given list of regions. `ALL_ENABLED` returns all
        enabled regions.

        Args:
            account_id: Account ID.
            regions: List of regions.

        Returns:
            List of regions.
        """
        if "ALL_ENABLED" in regions:
            return self.accounts[account_id]["EnabledRegions"]
        return [
            region
            for region in self.accounts[account_id]["EnabledRegions"]
            if region in regions
        ]

    def get_all_enabled_regions(self) -> List[str]:
        """Return a list of regions that are enabled in at least one account.

        Return:
            List of regions.
        """
        regions: Set[str] = set()
        for account in self.accounts.values():
            regions = regions | set(account["EnabledRegions"])
        return list(regions)

    def get_account_name(self, account_id: str) -> str:
        """Return the account name of a given account ID.

        Args:
            account_id: Account ID

        Returns:
            Account name
        """
        # The account ID may not exist in `self.accounts` a deployment was made
        # to an account that is not active anymore
        if not account_id in self.accounts:
            return "undefined"
        return self.accounts[account_id]["Name"]

    def account_region_exists(self, account_id: str, region: str) -> bool:
        """Return True if the account exists in the organization and the region
        is enabled in this account.

        Args:
            account_id: Account ID
            region: Region

        Returns:
            True if the account exists and the region is enabled.
        """
        if account_id in self.accounts:
            if region in self.accounts[account_id]["EnabledRegions"]:
                return True
        return False
