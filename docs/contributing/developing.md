---
layout: default
title: Developing engines
parent: Contributing
nav_order: 1
---

# Developing engines

To develop a new engine for AWS Orga Deployer, you will need to edit the source code. Feel free to make a pull request to share your contribution with the community!

In `src/aws_orga_deployer/engines`, create a new Python file whose name is the name of the new engine `<engine>.py`.

This Python file must declare a class `Engine` that inherit from `BaseEngine` and declare the methods `validate_module_config`, `prepare` and `postprocess`.

```python
from typing import Any, Dict, List

from aws_orga_deployer.engines import base
from aws_orga_deployer.package.store import ModuleAccountRegionKey


class Engine(base.BaseEngine):

    engine = "<engine_name_here>"  # Update the engine name
    default_included_patterns = ["*.ext"]  # Update this with a default list of filename patterns to include for the module hash
    default_excluded_patterns = []  # Update this with a default list of filename patterns to exclude for the module hash

    def validate_module_config(
        self,
        module_config: Dict[str, Any]
    ) -> None:
        """
        Args:
            module_config: Module configuration.

        Raises:
            AssertionError: In case of missing or invalid attributes
        """
        super().validate_module_config(module_config)
        # Your code here

    def prepare(
        self,
        key: ModuleAccountRegionKey,
        command: str,
        action: str,
        variables: Dict[str, Any],
        module_config: Dict[str, Any],
        deployment_cache_dir: str,
        engine_cache_dir: str,
    ) -> List[base.StepCommand]:
        """
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
        # Your code here

    def postprocess(
        self,
        key: ModuleAccountRegionKey,
        command: str,
        action: str,
        module_config: Dict[str, Any],
        deployment_cache_dir: str,
    ) -> base.StepOutcome:
        """Reads the file `output.json` created by the "wrapper" function and
        returns the outputs.

        Args:
            key: Step key to execute.
            command: CLI command requested.
            action: Action to be made ("create", "update", "destroy").
            module_config: Module configuration.
            deployment_cache_dir: Path to the module deployment cache directory.

        Returns:
            Outcome of the step.
        """
        # Your code here
```

* `validate_module_config`: Validate the content of the module configuration. You should use `assert` statements.
* `prepare`:
    * Prepare, if needed, input files stored in the deployment cache directory
    * Return a list of commands that are executed in subprocesses. This allows to isolate the execution of modules from the main process. The communication between the main process and subprocesses should be made via files stored in the deployment cache directory.
* `postprocess`: After subprocesses are executed, parse the output files and return the results of the module deployment to the orchestration function.

To test your module, your should extend the tests in `test_execution.py` and use the module configuration attribute `EndpointUrls` to specify a custom AWS endpoint that points to the `moto` server.
