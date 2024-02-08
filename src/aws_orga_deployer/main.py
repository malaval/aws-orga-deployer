"""Main program module."""

import sys

from aws_orga_deployer import cli, config, execution, modules, utils
from aws_orga_deployer.orga import OrgaParser
from aws_orga_deployer.package import Package


def main() -> None:
    """Main function."""

    # pylint: disable=broad-exception-caught
    # We want to catch any exceptions that was uncatched before

    # Parse CLI arguments and retrieve a logger for this module
    logger = cli.init_cli()
    try:
        # Load modules and package configuration settings, and retrieve
        # information about AWS accounts and organizational units. The
        # `OrgaParser` must be instantiated after `Package` because it needs
        # settings from the package definition file
        modules.load_modules()
        package = Package()
        orga = OrgaParser()

        # If the requested command is "orga", export details about the AWS
        # accounts and organizational units
        if config.CLI["command"] == "orga":
            utils.write_output_json(
                orga.export(),
                "AWS account list and organization structure",
            )
            return

        # Retrieve deployed modules and determine the changes to be made. This
        # is not needed for the command "orga"
        package.full_init(orga)

        # If the requested command is "remove-orphans", remove the module
        # deployments to destroy that correspond to accounts that no longer
        # exist in the organization, or regions that are not longer enabled in
        # an account
        if config.CLI["command"] == "remove-orphans":
            dry_run = config.CLI["dry_run"]
            orphans_removed = package.remove_orphans(dry_run)
            utils.write_output_json(
                {"OrphanedDeployments": orphans_removed},
                "the list of orphaned module deployments",
            )
            if len(orphans_removed) > 0 and config.CLI["detailed_exitcode"]:
                sys.exit(2)
            sys.exit(0)

        # Determine changes to be made
        has_pending_changes = package.analyze_changes()

        # If the requested command is "list", export details about deployed
        # modules and changes to be made
        if config.CLI["command"] == "list":
            utils.write_output_json(
                package.export_changes(),
                "the list of deployed modules and changes to be made",
            )
            if has_pending_changes and config.CLI["detailed_exitcode"]:
                sys.exit(2)
            sys.exit(0)

        # If there are no changes to be made, the commands "preview",
        # "apply" or "update-hash" can be interrupted
        if not has_pending_changes:
            sys.exit(0)

        # Print information about the requested command
        if config.CLI["command"] == "preview":
            logger.info(
                '"preview" will determine which resources to add, update or delete if'
                " the pending deployments are applied"
            )
        elif config.CLI["command"] == "apply":
            logger.info(
                '"apply" will apply pending deployments, resulting in the creation,'
                " update or deletion of resources"
            )
        elif config.CLI["command"] == "update-hash":
            logger.info(
                '"update-hash" will update the value of the module hash for deployments'
                " to update"
            )

        # Ask confirmation of the deployment scope, unless the tool is used
        # in non-interactive mode
        if not config.CLI["non_interactive"]:
            val = input(
                'Enter "yes" to confirm the deployment scope (use the command "list"'
                " for details): "
            )
            if val != "yes":
                sys.exit(0)

        # Launch execution
        executor = execution.Executor(package)
        executor.run()

        # Display and export execution results
        made_changes, has_failed = package.analyze_results()
        utils.write_output_json(
            package.export_results(),
            "the result of the execution",
        )
        if has_failed:
            sys.exit(1)
        if made_changes and config.CLI["detailed_exitcode"]:
            sys.exit(2)
        sys.exit(0)

    except KeyboardInterrupt:
        logger.critical("Interrupted")
        sys.exit(1)
    except Exception as err:
        logger.critical(err, exc_info=config.CLI["debug"])
        sys.exit(1)


if __name__ == "__main__":
    main()
