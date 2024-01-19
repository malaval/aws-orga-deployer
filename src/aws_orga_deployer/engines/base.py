"""Base class inherited by engine classes."""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from aws_orga_deployer import config
from aws_orga_deployer.package.store import ModuleAccountRegionKey

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


@dataclass
class StepCommand:
    """Details about a subprocess to execute.

    Attributes:
        name: Friendly name for the subprocess
        args: List of subprocess arguments.
        cwd: Current working directory of the subprocess.
        assume_role: True if the IAM role must be assumed and AWS temporary
            credentials must be provided as environment variables to the
            subprocess.
        env: Additional environment variables to pass to the subprocess.
            Default to an empty dict (no additional environment variables).
        stdout_file: To save the content of the subprocess standard output
            `stdout` to a file, provide a file path.
    """

    name: str
    args: List[str]
    cwd: str
    assume_role: bool
    env: Dict[str, str] = field(default_factory=dict)
    stdout_file: Optional[str] = None


@dataclass
class StepOutcome:
    """Contains the results of the step execution.

    Attributes:
        made_changes: True if the step resulted in changes made or to be made.
        result: Summary of the result.
        detailed_results: Optional detailed results, such as the list of
            resources added, changed or deleted. Should only be valued for
            completed steps.
        outputs: Outputs returned when the step has completed. Should be valued
            only when the command is "apply" and if the action is not "destroy".
    """

    made_changes: bool
    result: str
    detailed_results: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None


class BaseEngine:
    """Base class inherited by engine classes.

    Attributes:
        name: Name of the module.
        engine: Name of the engine.
        module_dir: Path to the module directory.
        default_included_patterns: Default file patterns to include for
            computing the module hash of all modules for this engine, if no
            custom hash configuration is provided.
        default_excluded_patterns: Default file patterns to exclude for
            computing the module hash of all modules for this engine, if no
            custom hash configuration is provided.
        included_patterns: File patterns to include for this module (custom if
            a hash configuration file exists, or default).
        excluded_patterns: File patterns to exclude for this module (custom if
            a hash configuration file exists, or default).
        module_hash: Module hash.
    """

    # Default class attributes to override by engine classes
    engine: str = ""
    module_dir: str
    default_included_patterns: List[str] = ["*"]
    default_excluded_patterns: List[str] = []
    included_patterns: List[str]
    excluded_patterns: List[str]

    def __init__(self, name: str, path: str) -> None:
        """Create a BaseEngine instance.

        Args:
            name: Name of the module
            path: Path of module files
        """
        self.name = name
        self.module_dir = path
        self._get_filename_patterns_to_hash()
        self.module_hash = self._generate_module_hash()

    def _generate_module_hash(self) -> str:
        """Return the MD5 hash of the module."""
        return self._md5_update_from_dir(self.module_dir, hashlib.md5()).hexdigest()

    def _get_filename_patterns_to_hash(self) -> None:
        """Set the values of `self.included_patterns` and
        `self.excluded_patterns` that define the patterns of file names to
        use for computing the module hash.
        """
        self.included_patterns = self.default_included_patterns.copy()
        self.excluded_patterns = self.default_excluded_patterns.copy()
        try:
            # Load the hash configuration file if it exists in this module
            filename = os.path.join(self.module_dir, config.HASH_CONFIG_FILENAME)
            with open(filename, "rb") as stream:
                content = json.load(stream)
                assert isinstance(content, dict)
                if "Include" in content:
                    self.included_patterns = content["Include"]
                if "Exclude" in content:
                    self.excluded_patterns = content["Exclude"]
                for check in (self.included_patterns, self.excluded_patterns):
                    assert isinstance(check, list)
                    assert all(isinstance(item, str) for item in check)
            LOGGER.debug(
                "[%s] Found hash-config.json: Include=%s Exclude=%s",
                self.name,
                ",".join(self.included_patterns),
                ",".join(self.excluded_patterns),
            )
        except (FileNotFoundError, IOError):
            LOGGER.debug(
                "[%s] No hash-config.json file found. Using default: Include=%s"
                " Exclude=%s",
                self.name,
                ",".join(self.included_patterns),
                ",".join(self.excluded_patterns),
            )
        except (ValueError, AssertionError):
            LOGGER.debug(
                "[%s] hash-config.json is invalid. Using default: Include=%s"
                " Exclude=%s",
                self.name,
                ",".join(self.included_patterns),
                ",".join(self.excluded_patterns),
            )

    @staticmethod
    def _md5_update_from_file(filename: str, dir_hash: Any) -> Any:
        """Update the MD5 hash with a file."""
        assert Path(filename).is_file()
        with open(str(filename), "rb") as stream:
            for chunk in iter(lambda: stream.read(4096), b""):
                dir_hash.update(chunk)
        return dir_hash

    def _md5_update_from_dir(self, directory: str, dir_hash: Any) -> Any:
        """Update the MD5 hash by browsing files and folders recursively. Only
        the file names matching the patterns are used to compute the hash.
        """
        assert Path(directory).is_dir()
        # For each file or folder in this directory
        for path in sorted(Path(directory).iterdir()):
            # Browse subfolders recursively
            if path.is_dir():
                dir_hash = self._md5_update_from_dir(str(path), dir_hash)
            elif path.is_file():
                # Check that the filename matches one of the included patterns,
                # and not any of the excluded filename patterns. The hash
                # configuration file is also excluded
                is_included = False
                is_excluded = False
                for pattern in self.included_patterns:
                    expr = re.escape(pattern).replace("\\*", ".*").lower()
                    if re.match(expr, path.name.lower()):
                        is_included = True
                        break
                for pattern in self.excluded_patterns:
                    expr = re.escape(pattern).replace("\\*", ".*").lower()
                    if re.match(expr, path.name.lower()):
                        is_excluded = True
                        break
                if (
                    not is_included
                    or is_excluded
                    or path.name.endswith(config.HASH_CONFIG_FILENAME)
                ):
                    continue
                # Update the hash with the file name and content
                dir_hash.update(path.name.encode())
                dir_hash = BaseEngine._md5_update_from_file(str(path), dir_hash)
        return dir_hash

    def validate_module_config(self, module_config: Dict[str, Any]) -> None:
        """Validate the content of the module configuration.

        Args:
            module_config: Module configuration.

        Raises:
            AssertionError
        """
        # Check that AssumeRole is None or a string
        assume_role = module_config.get("AssumeRole")
        assert assume_role is None or isinstance(
            assume_role, str
        ), 'AssumeRole must be "null" or a string'
        # Check Retry parameters
        if "Retry" in module_config:
            if "MaxAttempts" in module_config["Retry"]:
                max_attempts = module_config["Retry"]["MaxAttempts"]
                assert isinstance(max_attempts, int), "MaxAttempts must be an integer"
                assert max_attempts > 0, "MaxAttempts must be larger than 0"
            if "DelayBeforeRetrying" in module_config["Retry"]:
                delay = module_config["Retry"]["DelayBeforeRetrying"]
                assert isinstance(delay, int), "DelayBeforeRetrying must be an integer"
                assert (
                    delay >= 0
                ), "DelayBeforeRetrying must be larger than or equal to 0"
        # Check EndpointUrls
        if "EndpointUrls" in module_config:
            assert isinstance(
                module_config["EndpointUrls"], dict
            ), "EndpointUrls must be a dict"

    def prepare(
        self,
        key: ModuleAccountRegionKey,
        command: str,
        action: str,
        variables: Dict[str, Any],
        module_config: Dict[str, Any],
        deployment_cache_dir: str,
        engine_cache_dir: str,
    ) -> List[StepCommand]:
        """Prepare inputs and return a list of commands to execute in
        subprocesses.

        Args:
            key: Step key to execute.
            command: CLI command requested ("preview" or "deploy").
            action: Action to be made ("create", "update" or "destroy").
            variables: Input variables.
            module_config: Module configuration.
            deployment_cache_dir: Path to the module deployment cache directory.
            engine_cache_dir: Path to the engine cache directory (common to all
                modules for this engine).

        Returns:
            List of commands to execute in subprocesses.
        """
        raise NotImplementedError

    def postprocess(
        self,
        key: ModuleAccountRegionKey,
        command: str,
        action: str,
        module_config: Dict[str, Any],
        deployment_cache_dir: str,
    ) -> StepOutcome:
        """Parse the files that are generated by the subprocesses and return
        step outcomes.

        Args:
            key: Step key to execute.
            command: CLI command requested.
            action: Action to be made ("create", "update", "destroy").
            module_config: Module configuration.
            deployment_cache_dir: Path to the module deployment cache directory.

        Returns:
            Outcomes of the step.
        """
        raise NotImplementedError

    def write_wrapper_inputs(
        self,
        key: ModuleAccountRegionKey,
        command: str,
        action: str,
        variables: Dict[str, Any],
        module_config: Dict[str, Any],
        deployment_cache_dir: str,
        engine_cache_dir: str,
    ) -> None:
        """When using a Python wrapper script, write the inputs of the `prepare`
        function to a JSON file `input.json` that can be read by the wrapper.

        Args:
            key: Step key to execute.
            command: CLI command requested ("preview" or "deploy").
            action: Action to be made ("create", "update" or "destroy").
            variables: Input variables.
            module_config: Module configuration.
            deployment_cache_dir: Path to the module deployment cache directory.
            engine_cache_dir: Path to the engine cache directory (common to all
                modules for this engine).
        """
        # Prepare the content of the JSON file
        input_content: Dict[str, Any] = {
            "Deployment": key.to_dict(),
            "Command": command,
            "Action": action,
            "Variables": variables,
            "ModuleConfig": module_config,
            "ModulePath": self.module_dir,
            "DeploymentCacheDir": deployment_cache_dir,
            "EngineCacheDir": engine_cache_dir,
        }
        # Write the content to a file `input.json`
        input_file = os.path.join(deployment_cache_dir, "input.json")
        with open(input_file, "w", encoding="utf-8") as stream:
            json.dump(input_content, stream)

    def read_wrapper_outputs(self, deployment_cache_dir: str) -> StepOutcome:
        """When using a Python wrapper script, read the outputs of the wrapper
        script `output.json` and return a `StepOutcome` object.

        Args:
            deployment_cache_dir: Path to the module deployment cache directory.

        Returns:
            StepOutcome object.
        """
        output_file = os.path.join(deployment_cache_dir, "output.json")
        with open(output_file, "r", encoding="utf-8") as stream:
            content = json.load(stream)
            made_changes = content["MadeChanges"]
            result = content["Result"]
            detailed_results = content["DetailedResults"]
            outputs = content["Outputs"]
        return StepOutcome(made_changes, result, detailed_results, outputs)


def get_python_executable(module_config: Dict[str, Any]) -> str:
    """Return the path to the Python executable.

    Args:
        module_config: Module configuration.

    Returns:
        Path to the Python executable.
    """
    # Default value if no custom value is provided in the module configuration
    python_exec = "python3"
    if not module_config.get("PythonExecutable") is None:
        python_exec = module_config["PythonExecutable"]
    return python_exec
