"""Test the sub-package `package.engines`."""

# COMPLETED
from aws_orga_deployer.engines import ENGINES


def test_list_engines():
    """Check that the engines for python, terraform and cloudformation are
    successfully loaded.
    """
    for engine in ("python", "terraform", "cloudformation"):
        assert engine in ENGINES
