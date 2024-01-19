"""Test the module `aws_orga_deployer.modules`."""

# COMPLETED
import unittest

from aws_orga_deployer import config, modules
from tests import mock


class TestModules(unittest.TestCase):
    """Test the modules."""

    def setUp(self):
        """Load the modules."""
        mock.mock_cli_arguments(package_filename="package1.yaml")
        modules.load_modules()

    def test_modules(self):
        """Check that the modules are loaded."""
        self.assertIn("python1", config.MODULES)
        self.assertEqual(config.MODULES["python1"].engine, "python")

    def test_module_hash(self):
        """Check that the module "python1" has a module hash."""
        module_hash = config.MODULES["python1"].module_hash
        self.assertRegex(module_hash, "^[a-f0-9]{32}$")

    def test_patterns(self):
        """Check that the hash configuration file is correctly used."""
        self.assertEqual(
            config.MODULES["python1"].included_patterns,
            ["*.py"],
        )
        self.assertEqual(
            config.MODULES["python1"].excluded_patterns,
            ["~*.py"],
        )

    def test_module_config_python_invalid_1(self):
        """Check an invalid module configuration for Python modules."""
        module_config = {
            "AssumeRole": None,
            "Retry": {"MaxAttempts": 1, "DelayBeforeRetrying": 0},
            "PythonExecutable": [],
        }
        with self.assertRaises(AssertionError):
            config.MODULES["python1"].validate_module_config(module_config)

    def test_module_config_python_invalid_2(self):
        """Check an invalid module configuration for Python modules."""
        module_config = {"Retry": {"MaxAttempts": 0, "DelayBeforeRetrying": 0}}
        with self.assertRaises(AssertionError):
            config.MODULES["python1"].validate_module_config(module_config)

    def test_module_config_python_valid(self):
        """Check an valid module configuration for Python modules."""
        module_config = {}
        config.MODULES["python1"].validate_module_config(module_config)

    def test_module_config_cloudformation_invalid_1(self):
        """Check an invalid module configuration for CloudFormation modules."""
        module_config = {}
        with self.assertRaises(AssertionError):
            config.MODULES["cloudformation1"].validate_module_config(module_config)

    def test_module_config_cloudformation_invalid_2(self):
        """Check an invalid module configuration for CloudFormation modules."""
        module_config = {"StackName": "test"}
        with self.assertRaises(AssertionError):
            config.MODULES["cloudformation1"].validate_module_config(module_config)

    def test_module_config_cloudformation_valid(self):
        """Check an invalid module configuration for CloudFormation modules."""
        module_config = {"StackName": "test", "TemplateFilename": "template.yaml"}
        config.MODULES["cloudformation1"].validate_module_config(module_config)

    def test_module_config_terraform_invalid(self):
        """Check an invalid module configuration for CloudFormation modules."""
        module_config = {"TerraformExecutable": 1}
        with self.assertRaises(AssertionError):
            config.MODULES["terraform1"].validate_module_config(module_config)

    def test_module_config_terraform_valid(self):
        """Check an invalid module configuration for CloudFormation modules."""
        module_config = {"TerraformExecutable": "/bin/terraform"}
        config.MODULES["terraform1"].validate_module_config(module_config)
