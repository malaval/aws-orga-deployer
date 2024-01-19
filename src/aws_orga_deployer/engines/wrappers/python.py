"""Wrapper of Python modules that is executed in a subprocess."""

import importlib.util
import sys

from aws_orga_deployer.engines.wrappers import base


def main():
    """Main function."""
    # Read the inputs from the JSON file `input.json`
    inputs = base.read_wrapper_inputs()
    # Import the module Python script
    module_file = sys.argv[1]
    spec = importlib.util.spec_from_file_location("main", module_file)
    main_module = importlib.util.module_from_spec(spec)
    sys.modules["main"] = main_module
    spec.loader.exec_module(main_module)
    # Execute the main function of the module
    made_changes, result, detailed_results, outputs = main_module.main(
        inputs.module,
        inputs.account_id,
        inputs.region,
        inputs.command,
        inputs.action,
        inputs.variables,
        inputs.module_config,
        inputs.module_dir,
        inputs.deployment_cache_dir,
        inputs.engine_cache_dir,
    )
    # Write the outputs to a file as a JSON file
    base.write_wrapper_outputs(made_changes, result, detailed_results, outputs)


if __name__ == "__main__":
    main()
