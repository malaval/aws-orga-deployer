"""Module with classes used to store information about module deployments."""

# COMPLETED
import logging
import time
from collections import UserDict
from copy import deepcopy
from threading import Thread
from typing import Any, Dict, List

from aws_orga_deployer import config, utils

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class ModuleAccountRegionKey:
    """Hashable class that can be used as key for stores and graphes related
    to module deployments.

    Attributes:
        module: Module name
        account_id: Account ID
        region: Region
    """

    module: str
    account_id: str
    region: str

    def __init__(self, *args: Any):
        """A dict or 3 values (module, account_id, region) can be provided."""
        if len(args) > 1:
            self.module = args[0]
            self.account_id = args[1]
            self.region = args[2]
        else:
            self.module = args[0]["Module"]
            self.account_id = args[0]["AccountId"]
            self.region = args[0]["Region"]

    def __eq__(self, another: object) -> bool:
        if not isinstance(another, ModuleAccountRegionKey):
            return False
        return (
            self.module == another.module
            and self.account_id == another.account_id
            and self.region == another.region
        )

    def __hash__(self):
        return hash((self.module, self.account_id, self.region))

    def __str__(self):
        return f"[{self.module},{self.account_id},{self.region}]"

    def to_dict(self) -> Dict[str, str]:
        """Export to a dictionary."""
        return {
            "Module": self.module,
            "AccountId": self.account_id,
            "Region": self.region,
        }


class TargetDeploymentDetails:
    """Store details about a module deployment in the target state.

    Attributes:
        variables: Variables used for this module deployment.
        var_from_outputs: Variables populated from the outputs of other module
            deployments.
        dependencies: List of module deployments that must be created before or
            deleted after this module deployment.
        module_hash: Current value of the module hash.
    """

    variables: Dict[str, Any]
    var_from_outputs: Dict[str, Any]
    dependencies: List[Dict[str, str]]
    module_hash: str

    def __init__(
        self,
        variables: Dict[str, Any],
        var_from_outputs: Dict[str, Any],
        dependencies: List[Dict[str, str]],
        module_hash: str,
    ) -> None:
        self.variables = variables
        self.var_from_outputs = var_from_outputs
        self.dependencies = dependencies
        self.module_hash = module_hash

    def __eq__(self, another: object) -> bool:
        if not isinstance(another, TargetDeploymentDetails):
            return False
        return (
            self.variables == another.variables
            and self.var_from_outputs == another.var_from_outputs
            and self.dependencies == another.dependencies
            and self.module_hash == another.module_hash
        )

    def to_dict(self) -> Dict[str, Any]:
        """Export to a dictionary."""
        return {
            "Variables": self.variables,
            "VariablesFromOutputs": self.var_from_outputs,
            "Dependencies": self.dependencies,
            "ModuleHash": self.module_hash,
        }


class CurrentDeploymentDetails:
    """Store details about a module deployment in the current state.

    Attributes:
        variables: Variables used for this module deployment.
        var_from_outputs: Variables populated from the outputs of other module
            deployments.
        dependencies: List of module deployments that must be created before or
            deleted after this module deployment.
        module_hash: Value of the module hash when the deployment was made.
        outputs: Outputs returned by this module deployment.
        last_changed_time: Last time this module deployment was changed.
    """

    variables: Dict[str, Any]
    var_from_outputs: Dict[str, Any]
    dependencies: List[Dict[str, str]]
    module_hash: str
    outputs: Dict[str, Any]
    last_changed_time: str

    def __init__(self, *args: Any, **kwargs: Any):
        """A dict generated with `to_dict` or 4 values can be provided."""
        if len(args) > 0 and isinstance(args[0], dict):
            self.variables = args[0]["Variables"]
            self.var_from_outputs = args[0]["VariablesFromOutputs"]
            self.dependencies = args[0]["Dependencies"]
            self.module_hash = args[0]["ModuleHash"]
            self.outputs = args[0]["Outputs"]
            self.last_changed_time = args[0]["LastChangedTime"]
        else:
            self.variables = args[0] if len(args) > 0 else kwargs["variables"]
            self.var_from_outputs = (
                args[1] if len(args) > 1 else kwargs["var_from_outputs"]
            )
            self.dependencies = args[2] if len(args) > 2 else kwargs["dependencies"]
            self.module_hash = args[3] if len(args) > 3 else kwargs["module_hash"]
            self.outputs = args[4] if len(args) > 4 else kwargs["outputs"]
            self.last_changed_time = (
                args[5] if len(args) > 5 else kwargs["last_changed_time"]
            )

    def __eq__(self, another: object) -> bool:
        if not isinstance(another, CurrentDeploymentDetails):
            return False
        return (
            self.variables == another.variables
            and self.var_from_outputs == another.var_from_outputs
            and self.dependencies == another.dependencies
            and self.outputs == another.outputs
            and self.module_hash == another.module_hash
            and self.last_changed_time == another.last_changed_time
        )

    def to_dict(self) -> Dict[str, Any]:
        """Export to a dictionary."""
        return {
            "Variables": self.variables,
            "VariablesFromOutputs": self.var_from_outputs,
            "Dependencies": self.dependencies,
            "ModuleHash": self.module_hash,
            "Outputs": self.outputs,
            "LastChangedTime": self.last_changed_time,
        }


class CurrentStateStore(UserDict):
    """Class that loads and saves the content of a dictionay from S3. The
    keys must be of type ModuleAccountRegionKey and the values must be of type
    CurrentDeploymentDetails.

    Attributes:
        period: Frequency at which the package state is saved to S3. If the
            period is 0, the periodic saving is disabled.
    """

    period: int

    def __init__(self, period: int = 0):
        def func() -> None:
            # pylint: disable = bare-except
            # We need to catch any exceptions so that this thread never stops

            while True:
                try:
                    time.sleep(period)
                    if self._must_stop is True:
                        return
                    self.save()
                except:
                    LOGGER.exception(
                        "Failed to save the package state to S3",
                        exc_info=config.CLI["debug"],
                    )

        # Load and deserialize the content from S3 if the package state exists.
        # If the file does not exist in S3, start with a blank dict
        dict_content = {}
        try:
            serialized = utils.load_json_from_s3(config.STATE_FILENAME)
            current_deployments = serialized["Deployments"]
            for item in current_deployments:
                key = ModuleAccountRegionKey(item["Deployment"])
                value = CurrentDeploymentDetails(item["CurrentState"])
                dict_content[key] = value
        except utils.FileNotExists:
            pass
        super().__init__(dict_content)
        self._must_stop: bool = False
        self._data_copy: Dict = deepcopy(self.data)
        # Initialize a thread that saves the state every `period` seconds if it
        # has changed since the last time it was saved to S3, unless disabled.
        if period > 0:
            Thread(target=func, daemon=True, name="CurrentStateStore").start()

    def save(self) -> bool:
        """Save the content to S3 if it has changed since the last time it was
        saved.

        Returns:
            True if the package state was saved to S3, False if no change was
                found.
        """
        if self.data == self._data_copy:
            return False
        LOGGER.debug("Saving the package state to S3")
        # Serialize the package state into a JSON document that contains a list
        # of current deployments, and each current deployment is a dict with:
        #
        # {
        #   `Deployment`: `ModuleAccountRegionKey.to_dict()`
        #   `CurrentState`: `CurrentDeploymentDetails.to_dict()`
        # }
        current_deployments = []
        for key, value in self.data.items():
            item = {"Deployment": key.to_dict(), "CurrentState": value.to_dict()}
            current_deployments.append(item)
        serialized = {"Deployments": current_deployments}
        # Write the file to S3, and store a copy of the content saved to S3
        # so that we can evaluate if the content has changed since the last
        # save to S3.
        utils.write_dict_to_s3(serialized, config.STATE_FILENAME)
        self._data_copy = deepcopy(self.data)
        return True

    def stop(self) -> None:
        """Force the daemon thread that saves the current stat at regular
        intervals to stop.
        """
        self._must_stop = True
