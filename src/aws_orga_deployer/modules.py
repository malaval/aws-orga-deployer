"""Load modules."""

# COMPLETED
import logging
import os
from typing import Dict

from aws_orga_deployer import config
from aws_orga_deployer.engines import ENGINES
from aws_orga_deployer.engines.base import BaseEngine

LOGGER = logging.getLogger(__name__)  # pylint: disable=invalid-name
LOGGER.addHandler(logging.NullHandler())


class ModuleError(Exception):
    """Exception raised when the package contains invalid modules."""


def load_modules() -> None:
    """Instantiate the Engine class for each module and store them in a
    dict in `config.MODULES`.
    """
    modules: Dict[str, BaseEngine] = {}
    modules_stats: Dict[str, int] = {}
    # The modules must be in the same folder than the package file. The
    # first level of subfolders correspond to the engine, the second to the
    # modules
    package_path = os.path.dirname(os.path.abspath(config.CLI["package_file"]))
    # For each type of engine
    for engine, engine_class in ENGINES.items():
        engine_path = os.path.join(package_path, engine)
        # If there is a folder for this engine, list the subfolders and load
        # modules
        if os.path.exists(engine_path):
            for filename in os.listdir(engine_path):
                fullpath = os.path.join(engine_path, filename)
                if os.path.isdir(fullpath):
                    # Module names must be unique
                    if filename in modules:
                        raise ModuleError(f"The module {filename} already exists")
                    modules[filename] = engine_class(filename, fullpath)
                    modules_stats.setdefault(engine, 0)
                    modules_stats[engine] += 1
    # Save the modules in `config.MODULES` for reuse by other modules, and print
    # module stats
    config.MODULES = modules
    LOGGER.info(
        "Found %s modules in this package (%s)",
        len(modules),
        ", ".join([f"{number} {engine}" for engine, number in modules_stats.items()]),
    )
