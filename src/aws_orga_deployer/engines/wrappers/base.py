"""Base functions for wrapper scripts."""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class WrapperInputs:
    """Store inputs that are read from the JSON file `input.json`.

    Attributes:
        module: Deployment module.
        account_id: Deployment AWS account ID.
        region: Deployment region.
        command: CLI command requested ("preview" or "deploy").
        action: Action to be made ("create", "update" or "destroy").
        variables: Input variables.
        module_config: Module configuration.
        module_dir: Path to the module directory.
        deployment_cache_dir: Path to the module deployment cache directory.
        engine_cache_dir: Path to the engine cache directory (common to all
            modules for this engine).
    """

    module: str
    account_id: str
    region: str
    command: str
    action: str
    variables: Dict[str, Any]
    module_config: Dict[str, Any]
    module_dir: str
    deployment_cache_dir: str
    engine_cache_dir: str


def read_wrapper_inputs() -> WrapperInputs:
    """Read the inputs to the wrapper function from the file `input.json`.

    Returns:
        WrapperInputs object.
    """
    with open("input.json", "r", encoding="utf-8") as stream:
        content = json.load(stream)
        return WrapperInputs(
            module=content["Deployment"]["Module"],
            account_id=content["Deployment"]["AccountId"],
            region=content["Deployment"]["Region"],
            command=content["Command"],
            action=content["Action"],
            variables=content["Variables"],
            module_config=content["ModuleConfig"],
            module_dir=content["ModulePath"],
            deployment_cache_dir=content["DeploymentCacheDir"],
            engine_cache_dir=content["EngineCacheDir"],
        )


def write_wrapper_outputs(
    made_changes: bool,
    result: str,
    detailed_results: Optional[Dict[str, Any]] = None,
    outputs: Optional[Dict[str, Any]] = None,
) -> None:
    """Write the outcomes of the wrapper function to a file `output.json`.

    Args:
        made_changes: True if the step resulted in changes made or to be made.
        result: Summary of the result.
        detailed_results: Optional detailed results, such as the list of
            resources added, changed or deleted. Should only be valued for
            completed steps.
        outputs: Outputs returned when the step has completed. Should be valued
            only when the command is "apply" and if the action is not "destroy".
    """
    output_content = {
        "MadeChanges": made_changes,
        "Result": result,
        "DetailedResults": detailed_results,
        "Outputs": outputs,
    }
    with open("output.json", "w", encoding="utf-8") as stream:
        json.dump(output_content, stream)
