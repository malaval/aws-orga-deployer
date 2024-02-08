"""Load the package definition file and determine the modules to deploy."""

import json
import logging
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from aws_orga_deployer import config
from aws_orga_deployer.orga import OrgaParser
from aws_orga_deployer.package import schema
from aws_orga_deployer.package.graph import DeploymentGraph
from aws_orga_deployer.package.store import (
    CurrentDeploymentDetails,
    CurrentStateStore,
    ModuleAccountRegionKey,
    TargetDeploymentDetails,
)

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class PackageError(Exception):
    """Exception raised when the package definition file is invalid."""

    def __init__(self, message: str) -> None:
        self.message = f"The package definition YAML file is invalid - {message}"
        super().__init__(self.message)


def _replace_keywords(source: Any, current_account_id: str, current_region: str) -> Any:
    """Replace any occurences of `${CURRENT_ACCOUNT_ID}` by `current_account_id`
    and of `${CURRENT_REGION}` by `current_region` recursively across lists and
    dictionaries.

    Args:
        source: Input object
        current_account_id (str): Value to replace `${CURRENT_ACCOUNT_ID}`
        current_region (str): Value to replace `${CURRENT_REGION}`
    """
    if isinstance(source, str):
        source = source.replace("${CURRENT_ACCOUNT_ID}", current_account_id)
        source = source.replace("${CURRENT_REGION}", current_region)
        return source
    if isinstance(source, dict):
        return {
            key: _replace_keywords(value, current_account_id, current_region)
            for key, value in source.items()
        }
    if isinstance(source, list):
        return [
            _replace_keywords(item, current_account_id, current_region)
            for item in source
        ]
    return source


class Package:
    """Class to load and parse the package definition file, determine the
    modules deployed and the changes to be made.
    """

    orga: OrgaParser
    current: CurrentStateStore
    target: Dict[ModuleAccountRegionKey, TargetDeploymentDetails]
    graph: DeploymentGraph
    cli_filters: Dict[str, Set]
    modules_config: Dict[str, Any]

    def __init__(self):
        """Load and validate the package definition file. This is needed to
        retrieve package configuration settings, such as the name of the bucket
        that stores persistent data.
        """
        # Attributes that will be populated by `full_init`
        self.orga = None
        self.current = None
        self.target = None
        self.graph = None
        self.cli_filters = None
        self.modules_config = None
        # Load the YAML file and validate its schema
        # pylint: disable=broad-exception-caught
        with open(config.CLI["package_file"], "r", encoding="utf-8") as stream:
            try:
                self.package = yaml.safe_load(stream)
                schema.validate(self.package)
            except Exception as err:
                raise PackageError(err) from err
        # Store the package configuration for use by other modules (attribute
        # `PackageConfiguration` of the YAML file)
        config.PACKAGE = self.package["PackageConfiguration"]

    def full_init(self, orga: OrgaParser) -> None:
        """Load additional elements needed for the CLI command `list`, `preview`
        or `deploy`: Determine the module deployments that should exist in the
        target state, the module deployments that currently exist by reading the
        package state file, and evaluate the changes to be made.

        Args:
            orga: Object to query for information on the accounts and the
                organizational units.
        """
        self.orga = orga
        self.target = {}
        self.modules_config = {}
        auto_save_period = config.CLI.get("save_state_every_seconds", 0)
        self.current = CurrentStateStore(period=auto_save_period)
        self.graph = DeploymentGraph()
        self._init_target_deployments()
        self._init_cli_filters()
        self._init_graph()

    def _init_target_deployments(self) -> None:
        """Determine the module deployments that must exist in the target
        state based on the package definition file.
        """
        for module, module_block in self.package["Modules"].items():
            # Determine the module configuration parameters for all deployments
            # of this module
            engine = config.MODULES[module].engine
            module_config = {}
            if "DefaultModuleConfiguration" in self.package:
                default_config = self.package["DefaultModuleConfiguration"]
                module_config.update(default_config.get("All", {}))
                module_config.update(default_config.get(engine, {}))
            module_config.update(module_block.get("Configuration", {}))
            # Validate the module configuration
            try:
                config.MODULES[module].validate_module_config(module_config)
            except AssertionError as err:
                raise PackageError(f"Configuration of {module}: {err}") from err
            self.modules_config[module] = module_config
            # For each deployment block, i.e. each item in the attribute
            # `Deployments`
            for deployment_block in module_block["Deployments"]:
                self._process_deployment_block(deployment_block, module)

    def _process_deployment_block(
        self, deployment_block: Dict[str, Any], module: str
    ) -> None:
        """Process a deployment block, i.e. an item in the attribute
        `Deployments` of a module in the package definition file, to determine
        the expected module deployments.

        Args:
            deployment_block: Content of the deployment block
            module: Module name
        """
        engine = config.MODULES[module].engine
        module_block = self.package["Modules"][module]
        # Determine the variables
        variables_block = {}
        if "DefaultVariables" in self.package:
            default_variables = self.package["DefaultVariables"]
            variables_block.update(default_variables.get("All", {}))
            variables_block.update(default_variables.get(engine, {}))
        variables_block.update(module_block.get("Variables", {}))
        variables_block.update(deployment_block.get("Variables", {}))
        # Determine the dependencies
        dependencies_block = deployment_block.get("Dependencies", [])
        var_from_outputs_block = {}
        var_from_outputs_block.update(module_block.get("VariablesFromOutputs", {}))
        var_from_outputs_block.update(deployment_block.get("VariablesFromOutputs", {}))
        # Identify the list of accounts where to deploy the module for this
        # block. Filter or exclude accounts based on the `Include` or `Exclude`
        # attributes
        account_ids = set(self.orga.get_all_accounts())
        include = deployment_block.get("Include", {})
        if "AccountIds" in include:
            tmp = self.orga.get_accounts_by_id(include["AccountIds"])
            account_ids = account_ids & set(tmp)
        if "AccountNames" in include:
            tmp = self.orga.get_accounts_by_name(include["AccountNames"])
            account_ids = account_ids & set(tmp)
        if "AccountTags" in include:
            tmp = self.orga.get_accounts_by_tag(include["AccountTags"])
            account_ids = account_ids & set(tmp)
        if "OUIds" in include:
            tmp = self.orga.get_accounts_by_ou(include["OUIds"])
            account_ids = account_ids & set(tmp)
        if "OUTags" in include:
            tmp = self.orga.get_accounts_by_ou_tag(include["OUTags"])
            account_ids = account_ids & set(tmp)
        exclude = deployment_block.get("Exclude", {})
        if "AccountIds" in exclude:
            tmp = self.orga.get_accounts_by_id(exclude["AccountIds"])
            account_ids = account_ids - set(tmp)
        if "AccountNames" in exclude:
            tmp = self.orga.get_accounts_by_name(exclude["AccountNames"])
            account_ids = account_ids - set(tmp)
        if "AccountTags" in exclude:
            tmp = self.orga.get_accounts_by_tag(exclude["AccountTags"])
            account_ids = account_ids - set(tmp)
        if "OUIds" in exclude:
            tmp = self.orga.get_accounts_by_ou(exclude["OUIds"])
            account_ids = account_ids - set(tmp)
        if "OUTags" in exclude:
            tmp = self.orga.get_accounts_by_ou_tag(exclude["OUTags"])
            account_ids = account_ids - set(tmp)
        # For each account in the scope of the deployment block
        for account_id in account_ids:
            # Identify the regions where the module should be deployed. Start
            # from all enabled regions in the account and include and exclude
            # regions as defined by CLI arguments
            regions = set(self.orga.get_account_regions(account_id, ["ALL_ENABLED"]))
            if deployment_block.get("Include", {}).get("Regions"):
                tmp = self.orga.get_account_regions(
                    account_id, deployment_block["Include"]["Regions"]
                )
                regions = regions & set(tmp)
            if deployment_block.get("Exclude", {}).get("Regions"):
                tmp = self.orga.get_account_regions(
                    account_id, deployment_block["Exclude"]["Regions"]
                )
                regions = regions - set(tmp)
            # For each region targeted in the deployment scope for this account
            for region in regions:
                # Replace the keywords `${CURRENT_REGION}` and
                # `${CURRENT_ACCOUNT_ID}` by the current region and account ID.
                # The variables ending with `_block` are deep copied because
                # the value `${CURRENT_REGION}` is replaced by the current
                # region, so we cannot use the same objects for all regions.
                dependencies = _replace_keywords(
                    deepcopy(dependencies_block), account_id, region
                )
                var_from_outputs = _replace_keywords(
                    deepcopy(var_from_outputs_block), account_id, region
                )
                variables = _replace_keywords(
                    deepcopy(variables_block), account_id, region
                )
                # Add the target deployment
                key = ModuleAccountRegionKey(module, account_id, region)
                self.target[key] = TargetDeploymentDetails(
                    variables=variables,
                    var_from_outputs=var_from_outputs,
                    dependencies=dependencies,
                    module_hash=config.MODULES[module].module_hash,
                )
                # Set the value the variables that depend on the outputs of
                # other module deployments
                self._set_variables_from_outputs(key)

    def _set_variables_from_outputs(self, t_key: ModuleAccountRegionKey) -> None:
        """For a given module deployment, set the value of its variables that
        depend on the outputs of other module deployments.

        Args:
            t_key: Step key for which variables must be updated with values
                of ascendant outputs
        """
        # Continue only if the module deployment exists in the current state
        # (not for "destroy")
        if not t_key in self.target:
            return
        t_content = self.target[t_key]
        # For each variable valued from the outputs of other module deployments
        for var_name, var_from in t_content.var_from_outputs.items():
            from_key = ModuleAccountRegionKey(
                var_from["Module"],
                var_from["AccountId"],
                var_from["Region"],
            )
            c_content = self.current.get(from_key)
            # If the source module deployment exists and has outputs, retrieve
            # the value of the output and modify the value of the variables
            if not c_content is None:
                if var_from["OutputName"] in c_content.outputs:
                    output_value = c_content.outputs.get(var_from["OutputName"])
                    t_content.variables[var_name] = output_value

    def _init_cli_filters(self) -> None:
        """Identify the filters defined by the CLI arguments `--include`
        and `--exclude` that restrict the modules, accounts or regions to
        deploy.
        """
        # Identify the deployments that the CLI arguments allow to create,
        # update or delete. Default to all existing modules.
        modules = set([*config.MODULES])
        if not config.CLI.get("include_modules") is None:
            modules = modules & set(config.CLI["include_modules"])
        if not config.CLI.get("exclude_modules") is None:
            modules = modules - set(config.CLI["exclude_modules"])
        # Identify the accounts that the CLI arguments allow to create,
        # update or delete. Default to all AWS accounts.
        account_ids = set(self.orga.get_all_accounts())
        if not config.CLI.get("include_account_ids") is None:
            tmp = self.orga.get_accounts_by_id(config.CLI["include_account_ids"])
            account_ids = account_ids & set(tmp)
        if not config.CLI.get("include_account_names") is None:
            tmp = self.orga.get_accounts_by_name(config.CLI["include_account_names"])
            account_ids = account_ids & set(tmp)
        if not config.CLI.get("include_account_tags") is None:
            tmp = self.orga.get_accounts_by_tag(config.CLI["include_account_tags"])
            account_ids = account_ids & set(tmp)
        if not config.CLI.get("include_ou_ids") is None:
            tmp = self.orga.get_accounts_by_ou(config.CLI["include_ou_ids"])
            account_ids = account_ids & set(tmp)
        if not config.CLI.get("include_ou_tags") is None:
            tmp = self.orga.get_accounts_by_ou_tag(config.CLI["include_ou_tags"])
            account_ids = account_ids & set(tmp)
        if not config.CLI.get("exclude_account_ids") is None:
            tmp = self.orga.get_accounts_by_id(config.CLI["exclude_account_ids"])
            account_ids = account_ids - set(tmp)
        if not config.CLI.get("exclude_account_names") is None:
            tmp = self.orga.get_accounts_by_name(config.CLI["exclude_account_names"])
            account_ids = account_ids - set(tmp)
        if not config.CLI.get("exclude_account_tags") is None:
            tmp = self.orga.get_accounts_by_tag(config.CLI["exclude_account_tags"])
            account_ids = account_ids - set(tmp)
        if not config.CLI.get("exclude_ou_ids") is None:
            tmp = self.orga.get_accounts_by_ou(config.CLI["exclude_ou_ids"])
            account_ids = account_ids - set(tmp)
        if not config.CLI.get("exclude_ou_tags") is None:
            tmp = self.orga.get_accounts_by_ou_tag(config.CLI["exclude_ou_tags"])
            account_ids = account_ids - set(tmp)
        # Identify the regions that the CLI arguments allow to create,
        # update or delete. Default to all enabled regions.
        regions = set(self.orga.get_all_enabled_regions())
        if not config.CLI.get("include_regions") is None:
            regions = regions & set(config.CLI["include_regions"])
        if not config.CLI.get("exclude_regions") is None:
            regions = regions - set(config.CLI["exclude_regions"])
        # Store resulting filters in a dict
        self.cli_filters = {
            "Modules": modules,
            "AccountIds": account_ids,
            "Regions": regions,
        }

    def _init_graph(self) -> None:
        self._add_graph_steps()
        self._add_graph_dependencies()
        self.graph.validate()

    def _add_graph_steps(self) -> None:
        # For each module deployment expected in the target state, check if
        # it must be created or updated
        for t_key, t_content in self.target.items():
            c_content = self.current.get(t_key)
            skip = self._is_skipped_by_cli_filters(t_key)
            # If the module deployment already exists, check if it must be
            # updated
            if not c_content is None:
                if self._check_update_needed(c_content, t_content):
                    action = "update"
                else:
                    action = "none"
            else:
                action = "create"
            max_attempts, delay = self._get_retry_parameters(t_key.module)
            self.graph.add_step(t_key, action, skip, max_attempts, delay)
        # For each module deployment that currently exists, check if it must be
        # deleted, i.e. if it should not exist in the target state
        for c_key, c_content in self.current.items():
            # When there are deployments to destroy, there must be a block in
            # the package definition file for this module to retrieve module
            # configuration parameters
            if not c_key.module in self.modules_config:
                raise PackageError(
                    f'There must be a block for the module "{c_key.module}" even with'
                    " an empty list of deployments"
                )
            if not c_key in self.target:
                skip = self._is_skipped_by_cli_filters(c_key)
                max_attempts, delay = self._get_retry_parameters(c_key.module)
                self.graph.add_step(c_key, "destroy", skip, max_attempts, delay)

    def _get_retry_parameters(self, module: str) -> Tuple[int, int]:
        """Return the retry parameters for a given module from the module
        configuration parameters.

        Args:
            module: Module name

        Returns:
            tuple:
                Maximum number of attempts. Default is 1
                Number of seconds to wait before retrying. Default is 0
        """
        if (
            not module in self.modules_config
            or not "Retry" in self.modules_config[module]
        ):
            return 1, 0
        max_attempts = self.modules_config[module]["Retry"].get("MaxAttempts", 1)
        delay = self.modules_config[module]["Retry"].get("DelayBeforeRetrying", 0)
        return max_attempts, delay

    def _check_update_needed(
        self, current: CurrentDeploymentDetails, target: TargetDeploymentDetails
    ) -> bool:
        """Return True if the module deployment must be updated because the
        current and target state differs, and because the CLI argument
        `--force-update` is set.

        Args:
            current: Current deployment details
            target: Target deployment details

        Returns:
            True if update is needed
        """
        return config.CLI.get("force_update", False) is True or not (
            current.module_hash == target.module_hash
            and current.variables == target.variables
        )

    def _add_graph_dependencies(self) -> None:
        # For each step in the graph, add dependencies as graph edges
        for to_key in self.graph.list_steps():
            # Get the corresponding module deployment details, either from the
            # list of the target deployments or current deployments
            to_details = self.target.get(to_key)
            if to_details is None:
                to_details = self.current[to_key]
            # Add dependencies defined by the `Dependencies` and/or
            # `VariablesFromOutputs` attributes. If a dependency is both in
            # `Dependencies` and `VariablesFromOutputs`, the latter prevails
            for dependency in to_details.dependencies:
                from_key = ModuleAccountRegionKey(
                    dependency["Module"],
                    dependency["AccountId"],
                    dependency["Region"],
                )
                ignore_if_not_exists = bool(dependency.get("IgnoreIfNotExists", False))
                self.graph.add_dependency(
                    from_key,
                    to_key,
                    is_var=False,
                    ignore_if_not_exists=ignore_if_not_exists,
                )
            for dependency in to_details.var_from_outputs.values():
                from_key = ModuleAccountRegionKey(
                    dependency["Module"],
                    dependency["AccountId"],
                    dependency["Region"],
                )
                ignore_if_not_exists = bool(dependency.get("IgnoreIfNotExists", False))
                self.graph.add_dependency(
                    from_key,
                    to_key,
                    is_var=True,
                    ignore_if_not_exists=ignore_if_not_exists,
                )

    def _is_skipped_by_cli_filters(self, key: ModuleAccountRegionKey) -> bool:
        """Check if a given module deployment should be skipped due to the CLI
        arguments.

        Args:
            key: Step key.

        Returns:
            True if skipped
        """
        return not (
            key.module in self.cli_filters["Modules"]
            and key.account_id in self.cli_filters["AccountIds"]
            and key.region in self.cli_filters["Regions"]
        )

    def next(self) -> Tuple[ModuleAccountRegionKey, str, int, int]:
        """Retrieve the next deployment to process and the action to make.
        Also update the value of the variables that eventually depends on the
        outputs of other module deployments.

        Returns:
            tuple:
                Step key
                Action to make. "conditional-update" is replaced by
                    "skipped" or "update" depending on whether output values
                    changed or not
                Current attempt number
                Maximum number of attempts

        Raises:
            aws_orga_deployer.package.graph.NoProcessableStep
            aws_orga_deployer.package.graph.NoMorePendingStep
        """
        while True:
            key = self.graph.next()
            details = self.graph.get_step_details(key)
            # If the command is "preview" and the step is dependent on other
            # steps with pending changes, changes to resources cannot be
            # previewed as they depend on a state that doesn't exist yet (e.g.
            # value of the dependent outputs). Therefore, the step is failed.
            if (
                config.CLI["command"] == "preview"
                and self.graph.has_ascendants_with_changes(key)
                and details.action != "destroy"
            ):
                message = (
                    "Unable to preview changes as this deployment is dependent on other"
                    " deployments with pending changes"
                )
                self.graph.fail(key, message)
                LOGGER.error("%s %s", key, message)
                continue
            # Update the variables with the latest values of the ascendant
            # outputs
            self._set_variables_from_outputs(key)
            if not details.action == "conditional-update":
                return key, details.action, details.nb_attempts, details.max_attempts
            # If the action is "conditional-update" and the value of the values
            # of the outputs on which depend the deployment have not changed,
            # skip the deployment
            current = self.current[key]
            target = self.target[key]
            if self._check_update_needed(current, target):
                return key, "update", details.nb_attempts, details.max_attempts
            self.graph.complete(
                key,
                False,
                "No changes required because the dependent output values have not"
                " changed",
            )

    def get_module_config(self, key: ModuleAccountRegionKey) -> Dict[str, Any]:
        """Return the module configuration for a given module deployment. The
        keywords `${CURRENT_ACCOUNT_ID}` and `${CURRENT_ACCOUNT}` are replaced
        by the account ID and region of the key.

        Args:
            key: Step key.

        Returns:
            Module configuration parameters
        """
        return _replace_keywords(
            deepcopy(self.modules_config[key.module]), key.account_id, key.region
        )

    def complete(
        self,
        key: ModuleAccountRegionKey,
        made_changes: bool,
        result: str,
        detailed_results: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a deployment as completed, and update the current package state
        if the command is "apply".

        Args:
            key: Step key
            made_changes: True if the step resulted in changes made or to be made
            result: One-line summary of the result.
            detailed_results: Dict with detailed results.
            outputs: Outputs returned by the module deployment, only when the
                action is not "destroy". Default is None to store an empty dict.
        """
        self.graph.complete(key, made_changes, result, detailed_results)
        # Update the current state store only if the command is "apply"
        if config.CLI["command"] == "apply":
            details = self.graph.get_step_details(key)
            # If the action is "destroy", remove it from the current state,
            # otherwise update the current state from the target state
            if details.action == "destroy":
                del self.current[key]
            else:
                self.current[key] = CurrentDeploymentDetails(
                    variables=self.target[key].variables,
                    var_from_outputs=self.target[key].var_from_outputs,
                    dependencies=self.target[key].dependencies,
                    module_hash=self.target[key].module_hash,
                    outputs=outputs if not outputs is None else {},
                    last_changed_time=str(datetime.utcnow()),
                )

    def fail(
        self,
        key: ModuleAccountRegionKey,
        result: str,
        detailed_results: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a deployment as failed.

        Args:
            key: Step key.
            result: One-line summary of the result.
            detailed_results: Dict with detailed results.
        """
        self.graph.fail(key, result, detailed_results)

    def update_hash(self, key: ModuleAccountRegionKey) -> bool:
        """Update the value of the module hash if the deployment action
        is "update". Then, mark the deployment as completed.

        Args:
            key: Step key.

        Returns:
            True if the module hash was updated, False otherwise
        """
        details = self.graph.get_step_details(key)
        if details.action == "update":
            if self.current[key].module_hash != self.target[key].module_hash:
                self.current[key].module_hash = self.target[key].module_hash
                self.current[key].last_changed_time = str(datetime.utcnow())
                self.graph.complete(key, True, "Updated the module hash")
                return True
        self.graph.complete(key, False, "No action needed")
        return False

    def save(self, stop_autosave: bool = False) -> None:
        """Save the current package state. Optionally stop the auto-save of the
        current state  That is particularly useful for testing because
        the auto-save might continue to write to S3 after the test has
        completed.

        Args:
            stop_autosave (bool): Stop the daemon thread of the current state
                store that saves the state to S3 at regular intervals.
        """
        self.current.save()
        if stop_autosave:
            self.current.stop()

    def analyze_changes(self) -> bool:
        """Display information about the changes to make and return whether
        there are pending changes to be made.

        Returns:
            bool: True if there are pending changes to be made.
        """
        result = {
            "create": {"pending": 0, "pending_skipped": 0},
            "update": {"pending": 0, "pending_skipped": 0},
            "conditional-update": {"pending": 0, "pending_skipped": 0},
            "destroy": {"pending": 0, "pending_skipped": 0},
        }
        # Count the number of changes to make
        pending_changes = 0
        for _, step in self.graph.list_steps_with_details():
            if step.action == "none":
                continue
            if step.skip:
                result[step.action]["pending_skipped"] += 1
            else:
                pending_changes += 1
                result[step.action]["pending"] += 1
        # Print the summary
        for action, prefix in (
            ("create", "Deployments to create"),
            ("update", "Deployments to update"),
            (
                "conditional-update",
                (
                    "Deployments thay may need updates if the outputs on which they"
                    " depend change"
                ),
            ),
            ("destroy", "Deployments to destroy"),
        ):
            if result[action]["pending"] + result[action]["pending_skipped"] > 0:
                message = prefix + ": %s (%s skipped due to CLI filters)"
                LOGGER.info(
                    message,
                    result[action]["pending"],
                    result[action]["pending_skipped"],
                )
        if pending_changes == 0:
            LOGGER.info("No changes to be made during this run")
        # Return True if there are pending changes that are not skipped
        return pending_changes > 0

    def export_changes(self) -> Dict[str, Any]:
        """Export the list of module deployments and changes to be made.

        Returns:
            dict: Dictionary whose structure is::

                {
                    "PendingChanges|PendingButSkippedChanges": {
                        "Create": [
                            {
                                "Deployment": {
                                    "Module" (str),
                                    "AccountId" (str),
                                    "AccountName" (str),
                                    "Region" (str)
                                },
                                "ModuleConfig" (dict): Module configuration,
                                "TargetState" (dict): Details about target state,
                            }
                        ],
                        "Update|ConditionalUpdate": [
                            {
                                "Deployment": {
                                    "Module" (str),
                                    "AccountId" (str),
                                    "AccountName" (str),
                                    "Region" (str)
                                },
                                "ModuleConfig" (dict): Module configuration,
                                "CurrentState" (dict): Details about current state,
                                "TargetState" (dict): Details about target state,
                            }
                        ],
                        "Destroy": [
                            {
                                "Deployment": {
                                    "Module" (str),
                                    "AccountId" (str),
                                    "AccountName" (str),
                                    "Region" (str)
                                },
                                "ModuleConfig" (dict): Module configuration,
                                "CurrentState" (dict): Details about current state,
                            }
                        ]
                    },
                    "NoChanges": [
                        {
                            "Deployment": {
                                "Module" (str),
                                "AccountId" (str),
                                "AccountName" (str),
                                "Region" (str)
                            },
                            "ModuleConfig" (dict): Module configuration,
                            "CurrentState" (dict): Details about current state,
                        }
                    ]
                }

        """

        def add_change(
            list_to_append: List,
            step_key: ModuleAccountRegionKey,
            show_current: bool,
            show_target: bool,
        ) -> None:
            """Add a description of a module deployment to the list
            `list_to_append` with details about current and/or target details.

            Args:
                list_to_append: Pointer to the list to which an item must be
                    added.
                key: Step key.
                show_current: True to include details of current state
                show_target: True to include details of target state
            """
            item: Dict[str, Any] = {}
            item["Deployment"] = key.to_dict()
            account_name = self.orga.get_account_name(key.account_id)
            item["Deployment"]["AccountName"] = account_name
            item["ModuleConfig"] = self.get_module_config(step_key)
            if show_current:
                item["CurrentState"] = self.current[step_key].to_dict()
            if show_target:
                item["TargetState"] = self.target[step_key].to_dict()
            list_to_append.append(item)

        result: Dict[str, Any] = {}
        for key, details in self.graph.list_steps_with_details():
            if details.action == "none":
                result.setdefault("NoChanges", [])
                add_change(result["NoChanges"], key, True, False)
                continue
            categ = "PendingButSkippedChanges" if details.skip else "PendingChanges"
            result.setdefault(categ, {})
            if details.action == "create":
                result[categ].setdefault("Create", [])
                add_change(result[categ]["Create"], key, False, True)
            elif details.action == "update":
                result[categ].setdefault("Update", [])
                add_change(result[categ]["Update"], key, True, True)
            elif details.action == "conditional-update":
                result[categ].setdefault("ConditionalUpdate", [])
                add_change(result[categ]["ConditionalUpdate"], key, True, True)
            elif details.action == "destroy":
                result[categ].setdefault("Destroy", [])
                add_change(result[categ]["Destroy"], key, True, False)
        return result

    def analyze_results(self) -> Tuple[bool, bool]:
        """Display information about the results and return changes to
        resources must be made or were made.

        Returns:
            Tuple:
                bool: True if changes to resources have to be made or were made.
                bool: True if some steps failed
        """
        completed = 0
        completed_with_changes = 0
        failed = 0
        pending = 0
        for _, step in self.graph.list_steps_with_details():
            if step.status == "completed":
                completed += 1
                if step.made_changes is True:
                    completed_with_changes += 1
            if step.status == "failed":
                failed += 1
            if step.status == "completed":
                pending += 0
        # Print the summary
        LOGGER.info(
            "%s deployments completed, %s failed, %s still pending",
            completed,
            failed,
            pending,
        )
        return completed_with_changes > 0, failed > 0

    def export_results(self) -> Dict[str, Any]:
        """Export the results of the package execution.

        Returns:
            dict: Dictionary whose structure is::

                {
                    "Completed|Failed|Pending": {
                        "Create|Update|ConditionalUpdate|Destroy": [
                            {
                                "Deployment": {
                                    "Module" (str),
                                    "AccountId" (str),
                                    "AccountName" (str),
                                    "Region" (str)
                                },
                                "NbAttempts" (str),
                                "Result" (str, optional),
                                "DetailedResults" (dict, optional),
                                "ResultedInChanges" (bool): Only for completed steps
                                "Outputs" (dict, optional): Only for completed steps
                                    when command is "apply" and action is not "destroy"
                            }
                        ]
                    }
                }

        """
        result: Dict[str, Any] = {}
        mapping_action = {
            "create": "Create",
            "update": "Update",
            "conditional-update": "ConditionalUpdate",
            "destroy": "Destroy",
        }
        for key, details in self.graph.list_steps_with_details():
            # Do not include deployments that were skipped in the results
            if details.status == "skipped":
                continue
            status = details.status.capitalize()
            action = mapping_action[details.action]
            result.setdefault(status, {})
            result[status].setdefault(action, [])
            item: Dict[str, Any] = {}
            item["Deployment"] = key.to_dict()
            account_name = self.orga.get_account_name(key.account_id)
            item["Deployment"]["AccountName"] = account_name
            item["NbAttempts"] = details.nb_attempts
            if details.result != "":
                item["Result"] = details.result
            if not details.detailed_results is None:
                item["DetailedResults"] = details.detailed_results
            # Only add `ResultedInChanges` if the step has completed
            if details.status == "completed":
                item["ResultedInChanges"] = details.made_changes
                # Only add `Outputs` if the step has completed and the
                # action is not "destroy", i.e. the deployment still exists
                # in the current state store
                if config.CLI["command"] == "apply" and key in self.current:
                    item["Outputs"] = self.current[key].outputs
            result[status][action].append(item)
        return result

    def remove_orphans(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """Remove the orphaned module deployments from the current state, which
        correspond to the module deployments for the accounts that not longer
        exist in the organization, or regions that are not longer enabled in
        the account.

        Args:
            dry_run: Set to True to return the list of orphans without making
                any changes.

        Returns:
            list: List of dictionaries of the following structure::

                {
                    "Module" (str),
                    "AccountId" (str),
                    "Region" (str)
                }

        """
        orphans_removed: List[Dict[str, Any]] = []
        keys = deepcopy(self.current.keys())
        for key in keys:
            if not self.orga.account_region_exists(key.account_id, key.region):
                orphans_removed.append(key.to_dict())
                if not dry_run:
                    del self.current[key]
        if dry_run:
            LOGGER.info(
                "Found %s orphaned module deployments to remove",
                len(orphans_removed),
            )
        else:
            self.current.save()
            LOGGER.info(
                "Removed %s orphaned module deployments",
                len(orphans_removed),
            )
        return orphans_removed
