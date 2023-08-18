"""General utility functions for test modules."""
from copy import deepcopy

from aws_orga_deployer import config


def update_cli_filters(new_params):
    """Update and return the values in a dict.

    Args:
        new_params (dict): Values to update.

    Returns:
        dict
    """
    cli_config = deepcopy(config.CLI)
    cli_config.update(new_params)
    return cli_config
