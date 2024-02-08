"""Parse command-line interface arguments."""

import argparse
import logging
import re
import sys
from os import path

from aws_orga_deployer import config


def _account_id_type(value: str) -> str:
    """Check that the value is an account ID."""
    pattern = re.compile(r"^[0-9]{12}$")
    if not pattern.match(value):
        raise argparse.ArgumentTypeError("Invalid format. Must be a 12-digit string")
    return value


def _tag_type(value: str) -> str:
    """Check that the value is in the form TAG_KEY=TAG_VALUE."""
    pattern = re.compile(r"^.+=.+$")
    if not pattern.match(value):
        raise argparse.ArgumentTypeError("Invalid format. Must be TAG_KEY=TAG_VALUE")
    return value


def _check_positive_int(value: str) -> int:
    """Check that the argument value is an integer larger than 0."""
    try:
        int_value = int(value)
        if int_value <= 0:
            raise argparse.ArgumentTypeError(f"{value} must be larger than zero")
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"{value} is not an integer") from err
    return int_value


def _parse_cli_args() -> None:
    """Parse the CLI arguments and store them in the variable `config.CLI`."""

    # Iniialize the parser and define global arguments
    parser = argparse.ArgumentParser(
        prog="aws-orga-deployer",
        description=(
            "AWS Orga Deployer: Deploy infrastructure-as-code at the scale of an AWS"
            " organization."
        ),
    )
    parser.add_argument(
        "-p",
        "--package-file",
        default=config.DEFAULT_PACKAGE_FILE,
        metavar="FILENAME",
        help=(
            "Location of the package definition YAML file."
            f" Default is {config.DEFAULT_PACKAGE_FILE}"
        ),
    )
    parser.add_argument(
        "-o",
        "--output-file",
        default=config.DEFAULT_OUTFILE_FILE,
        metavar="FILENAME",
        help=(
            "Location of the JSON file to which the command output details are written."
            f" Default is {config.DEFAULT_OUTFILE_FILE}"
        ),
    )
    parser.add_argument(
        "--temp-dir",
        default=config.DEFAULT_TEMP_DIR,
        metavar="DIRNAME",
        help=(
            "Location of the folder that stores cache and detailed log files. Default"
            f" is {config.DEFAULT_TEMP_DIR}"
        ),
    )
    parser.add_argument(
        "--force-orga-refresh",
        action="store_true",
        help=(
            "Ignore the cache in S3 and force the tool to query AWS Organizations for"
            " information on accounts and organizational unit"
        ),
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Increase log verbosity for debugging",
    )
    subparsers = parser.add_subparsers(title="command", dest="command")
    subparsers.required = True

    # Orga command
    subparsers.add_parser(
        "orga", help="Export AWS account list and organization structure"
    )

    # Detailed exit code
    parent_detailed_exitcode = argparse.ArgumentParser(add_help=False)
    parent_detailed_exitcode.add_argument(
        "--detailed-exitcode",
        action="store_true",
        help=(
            "Exit code is 0 if succeeded with no changes to be made, 1 if error, 2 if"
            " succeeded with changes present"
        ),
    )

    # Arguments that are common to the list, preview and apply commands
    parent_list_preview_apply = argparse.ArgumentParser(add_help=False)
    parent_list_preview_apply.add_argument(
        "-f",
        "--force-update",
        help=(
            "By default, modules are redeployed to a given AWS account and region only"
            " when the module hash or the variables changes. Add this argument to force"
            " module redeployment. Warning: this may result in a large number of"
            " deployments"
        ),
        action="store_true",
    )
    scope_group = parent_list_preview_apply.add_argument_group(
        title="filters",
        description=(
            "Restricts the deployment scope defined in the package configuration file,"
            " by excluding or including only certain modules, AWS accounts or regions."
        ),
    )
    scope_group.add_argument(
        "--include-modules",
        nargs="+",
        help="Include only certain modules",
        metavar="MODULE",
    )
    scope_group.add_argument(
        "--include-regions",
        nargs="+",
        help="Include only certain AWS regions",
        metavar="REGION",
    )
    scope_group.add_argument(
        "--include-account-ids",
        nargs="+",
        help="Include only certain AWS account IDs",
        metavar="ACCOUNT_ID",
        type=_account_id_type,
    )
    scope_group.add_argument(
        "--include-account-tags",
        nargs="+",
        help=(
            "Include only the AWS accounts with certain tags. Tags are cumulative, i.e."
            " KEY1=VALUE1 and KEY2=VALUE2 includes accounts with a tag KEY1 = VALUE1"
            " and with a tag TAG2 = VALUE2"
        ),
        metavar="KEY=VALUE",
        type=_tag_type,
    )
    scope_group.add_argument(
        "--include-account-names",
        nargs="+",
        help=(
            "Include only certain AWS account names. You can include wildcards (*) like"
            ' "*-prod"'
        ),
        metavar="ACCOUNT_NAME",
    )
    scope_group.add_argument(
        "--include-ou-ids",
        nargs="+",
        help="Include only certain organization unit IDs",
        metavar="OU_ID",
    )
    scope_group.add_argument(
        "--include-ou-tags",
        nargs="+",
        help=(
            "Include only the organizational units with certain tags. Tags are"
            " cumulative, i.e. KEY1=VALUE1 and KEY2=VALUE2 includes OUs with a tag KEY1"
            " = VALUE1 and with a tag TAG2 = VALUE2"
        ),
        metavar="KEY=VALUE",
        type=_tag_type,
    )
    scope_group.add_argument(
        "--exclude-modules", nargs="+", help="Exclude certain modules", metavar="MODULE"
    )
    scope_group.add_argument(
        "--exclude-regions",
        nargs="+",
        help="Exclude certain AWS regions",
        metavar="REGION",
    )
    scope_group.add_argument(
        "--exclude-account-ids",
        nargs="+",
        help="Exclude certain AWS account IDs",
        metavar="ACCOUNT_ID",
        type=_account_id_type,
    )
    scope_group.add_argument(
        "--exclude-account-tags",
        nargs="+",
        help=(
            "Exclude the AWS accounts with certain tags. Tags are cumulative, i.e."
            " KEY1=VALUE1 and KEY2=VALUE2 excludes accounts with a tag KEY1 = VALUE1"
            " and with a tag TAG2 = VALUE2"
        ),
        metavar="KEY=VALUE",
        type=_tag_type,
    )
    scope_group.add_argument(
        "--exclude-account-names",
        nargs="+",
        help=(
            "Exclude certain AWS account names. You can include wildcards (*) like"
            ' "*-prod"'
        ),
        metavar="ACCOUNT_NAME",
    )
    scope_group.add_argument(
        "--exclude-ou-ids",
        nargs="+",
        help="Exclude certain organization unit IDs",
        metavar="OU_ID",
    )
    scope_group.add_argument(
        "--exclude-ou-tags",
        nargs="+",
        help=(
            "Exclude the organizational units with certain tags. Tags are cumulative,"
            " i.e. KEY1=VALUE1 and KEY2=VALUE2 excludes OUs with a tag KEY1 = VALUE1"
            " and with a tag TAG2 = VALUE2"
        ),
        metavar="KEY=VALUE",
        type=_tag_type,
    )

    # List command
    subparsers.add_parser(
        "list",
        help="List deployed modules and deployments to create, update or destroy",
        parents=[parent_detailed_exitcode, parent_list_preview_apply],
    )

    # Arguments that are common to preview and apply commands
    parent_preview_apply = argparse.ArgumentParser(add_help=False)
    parent_preview_apply.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not ask to review and confirm the deployment scope",
    )
    parent_preview_apply.add_argument(
        "--keep-deployment-cache",
        action="store_true",
        help=(
            "Keep temporary files created during module deployment to enable"
            " troubleshooting"
        ),
    )

    # Arguments that are common to apply and update-hash
    parent_apply_update_hash = argparse.ArgumentParser(add_help=False)
    parent_apply_update_hash.add_argument(
        "--save-state-every-seconds",
        type=_check_positive_int,
        metavar="SECONDS",
        default=0,  # 0 means that package state is not saved periodically
        help=(
            "Save the package state periodically to S3 during execution to recover from"
            " an abrupt interruption. Specify a value in seconds larger than zero."
        ),
    )

    # Preview command
    subparsers.add_parser(
        "preview",
        help=(
            "Preview resources to add, update or delete when pending deployments are"
            " applied"
        ),
        parents=[
            parent_detailed_exitcode,
            parent_list_preview_apply,
            parent_preview_apply,
        ],
    )

    # Apply command
    subparsers.add_parser(
        "apply",
        help="Apply pending deployments",
        parents=[
            parent_detailed_exitcode,
            parent_list_preview_apply,
            parent_preview_apply,
            parent_apply_update_hash,
        ],
    )

    # Update-hash command
    subparsers.add_parser(
        "update-hash",
        help=(
            "Update the value of the module hash. This is useful to edit the"
            " module source code without needing to update deployments"
        ),
        parents=[
            parent_detailed_exitcode,
            parent_list_preview_apply,
            parent_preview_apply,
            parent_apply_update_hash,
        ],
    )

    # Arguments that are specific to the command "remove-orphans"
    remove_orphans = subparsers.add_parser(
        "remove-orphans",
        help=(
            "Remove orphaned module deployments from the package state corresponding to"
            " accounts that no longer exist in the AWS organization or regions that are"
            " no longer enabled in an account"
        ),
        parents=[parent_detailed_exitcode],
    )
    remove_orphans.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Return the list of orphaned module deployments to remove without making"
            " any changes"
        ),
    )

    # Parse the arguments and store them as a dict for use by other modules
    config.CLI = vars(parser.parse_args())
    # Use the absolute path of the temporary folder
    config.CLI["temp_dir"] = path.abspath(config.CLI["temp_dir"])


def _create_cli_logger() -> logging.Logger:
    """Create and return a logger for the CLI that writes to stdout.

    Returns:
        CLI logger
    """
    logger = logging.getLogger("aws_orga_deployer")
    logger.setLevel(logging.DEBUG if config.CLI["debug"] is True else logging.INFO)
    stream_handler = logging.StreamHandler(sys.stdout)
    if config.CLI["debug"] is True:
        log_format = "%(levelname)s %(threadName)s:%(name)s:%(funcName)s %(message)s"
    else:
        log_format = "%(levelname)s %(message)s"
    formatter = logging.Formatter(log_format)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def init_cli() -> logging.Logger:
    """Main function to parse CLI arguments and initialize a logger.

    Returns:
        CLI logger
    """
    _parse_cli_args()
    return _create_cli_logger()
