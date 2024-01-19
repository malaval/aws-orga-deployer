"""Modules for each supported engine."""

import os
from importlib import import_module
from typing import Any, Dict, List

# List the supported engines
engine_names: List[str] = [
    os.path.splitext(file)[0]
    for file in os.listdir(os.path.dirname(os.path.abspath(__file__)))
    if not file in ("__init__.py", "base.py") and file.endswith(".py")
]


# Load the class Engine of each supported module in a dict
ENGINES: Dict[str, Any] = {}
for engine_name in engine_names:
    module = import_module(f"aws_orga_deployer.engines.{engine_name}")
    ENGINES[engine_name] = module.Engine
