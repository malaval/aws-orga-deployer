"""Test the module `aws_orga_deployer.execution`."""

import shutil
import tempfile
import unittest
from unittest.mock import patch

import boto3
from moto import mock_cloudformation, mock_organizations, mock_s3, mock_ssm, mock_sts
from moto.server import ThreadedMotoServer

from aws_orga_deployer import modules
from aws_orga_deployer.execution import Executor
from aws_orga_deployer.orga import OrgaParser
from aws_orga_deployer.package import Package
from tests import mock
from tests.mock import mock_others
from tests.utils import update_cli_filters


class TestExecutor(unittest.TestCase):
    """Test the class Executor."""

    @mock_sts
    @mock_others
    def setUp(self):
        """Create resources that must exist for all tests."""
        mock.mock_cli_arguments(package_filename="package2.yaml")
        # Create a temporary folder for the test
        self.temp_dir = tempfile.mkdtemp()
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"temp_dir": self.temp_dir}),
        ):
            # We enable moto threaded server for CloudFormation and Terraform
            # testing as they are executed in separate subprocesses
            self.server = ThreadedMotoServer(verbose=False)
            self.server.start()
            # Enable mocking for S3 and Organizations in all tests without
            # having to add declarators to each test function
            self.mock_s3 = mock_s3()
            self.mock_s3.start()
            mock.create_fake_bucket()
            # Load modules
            modules.load_modules()
            # Enable persistent mocking for Organizations
            self.mock_organizations = mock_organizations()
            self.mock_organizations.start()
            # Create a fake AWS organization
            self.fake_orga = mock.FakeOrgaParser()
            # Create an OrgaParser object that queries the fake organization.
            # A Package object must be created first to load package configuration
            # settings, but it is unused after
            Package()
            self.orga = OrgaParser()

    def tearDown(self):
        """Disable mocking and delete common resources."""
        # Disable mocking
        self.mock_s3.stop()
        self.mock_organizations.stop()
        self.server.stop()
        # Delete the temporary folder
        shutil.rmtree(self.temp_dir)

    def test_python(self):
        """Test deployments with Python engine."""
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters(
                {"temp_dir": self.temp_dir, "include_modules": ["python1"]}
            ),
        ):
            package = Package()
            package.full_init(self.orga)
            executor = Executor(package)
            executor.run()
            export = package.export_results()
            self.assertEqual(len(export["Completed"]["Create"]), 1)
            # The detailed results are expected to contain the default AWS
            # account ID of moto (123456789012)
            self.assertEqual(
                export["Completed"]["Create"][0]["DetailedResults"]["AccountId"],
                "123456789012",
            )

    @mock_cloudformation
    @mock_ssm
    def test_cloudformation_preview(self):
        """Test to preview changes with the CloudFormation module."""
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({
                "temp_dir": self.temp_dir,
                "command": "preview",
                "include_modules": ["cloudformation1"],
            }),
        ):
            package = Package()
            package.full_init(self.orga)
            executor = Executor(package)
            executor.run()
            export = package.export_results()
            self.assertEqual(len(export["Completed"]["Create"]), 1)

    @mock_ssm
    @mock_cloudformation
    def test_cloudformation_create_destroy(self):
        """Test to create and destroy deployments with the CloudFormation
        module. Update cannot be tested because of a bug in moto:
        `create_change_set` fails with action is `UPDATE`. Also, moto does not
        return the stack outputs when a stack is created from a change set, and
        therefore cannot be tested.
        """
        ssm_client = boto3.client("ssm", region_name="eu-west-1")
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters(
                {"temp_dir": self.temp_dir, "include_modules": ["cloudformation1"]}
            ),
        ):
            # Create the deployment and check that one deployment was created
            # and the SSM parameter does exist
            package1 = Package()
            package1.full_init(self.orga)
            executor1 = Executor(package1)
            executor1.run()
            export1 = package1.export_results()
            self.assertEqual(len(export1["Completed"]["Create"]), 1)
            package1.save()
            parameter = ssm_client.get_parameter(Name="test")["Parameter"]
            self.assertEqual(parameter["Value"], "valueCloudFormation1")
            # Remove the deployments from the package, which requires to
            # destroy the existing deployment. Then, check that the SSM
            # parameter doesn't exist anymore
            package2 = Package()
            package2.package["Modules"]["cloudformation1"]["Deployments"] = []
            package2.full_init(self.orga)
            executor2 = Executor(package2)
            executor2.run()
            export2 = package2.export_results()
            self.assertEqual(len(export2["Completed"]["Destroy"]), 1)
            with self.assertRaises(ssm_client.exceptions.ParameterNotFound):
                parameter = ssm_client.get_parameter(Name="test")["Parameter"]

    @mock_ssm
    def test_terraform_preview(self):
        """Test to preview changes with the Terraform module."""
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({
                "temp_dir": self.temp_dir,
                "command": "preview",
                "include_modules": ["terraform1"],
            }),
        ):
            package = Package()
            package.full_init(self.orga)
            executor = Executor(package)
            executor.run()
            export = package.export_results()
            self.assertEqual(len(export["Completed"]["Create"]), 1)

    @mock_ssm
    def test_terraform_create_update_destroy(self):
        """Test to create, update and destroy deployments with the Terraform
        module.
        """
        ssm_client = boto3.client("ssm", region_name="eu-west-1")
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters(
                {"temp_dir": self.temp_dir, "include_modules": ["terraform1"]}
            ),
        ):
            # Create the deployment and check that one deployment was created
            # and the SSM parameter does exist
            package1 = Package()
            package1.full_init(self.orga)
            executor1 = Executor(package1)
            executor1.run()
            export1 = package1.export_results()
            package1.save()
            self.assertEqual(len(export1["Completed"]["Create"]), 1)
            self.assertIn(
                "SSMParameterARN", export1["Completed"]["Create"][0]["Outputs"]
            )
            parameter = ssm_client.get_parameter(Name="test")["Parameter"]
            self.assertEqual(parameter["Value"], "valueTerraform1")
            # Update the deployment by changing the value of the variable
            package2 = Package()
            vars_module = package2.package["Modules"]["terraform1"]["Variables"]
            vars_module["varTerraform1"] = "newValue"
            package2.full_init(self.orga)
            executor2 = Executor(package2)
            executor2.run()
            export2 = package2.export_results()
            package2.save()
            self.assertEqual(len(export2["Completed"]["Update"]), 1)
            parameter = ssm_client.get_parameter(Name="test")["Parameter"]
            self.assertEqual(parameter["Value"], "newValue")
            # Remove the deployments from the package, which requires to
            # destroy the existing deployment. Then, check that the SSM
            # parameter doesn't exist anymore
            package3 = Package()
            package3.package["Modules"]["terraform1"]["Deployments"] = []
            package3.full_init(self.orga)
            executor3 = Executor(package3)
            executor3.run()
            export3 = package3.export_results()
            self.assertEqual(len(export3["Completed"]["Destroy"]), 1)
            with self.assertRaises(ssm_client.exceptions.ParameterNotFound):
                parameter = ssm_client.get_parameter(Name="test")["Parameter"]
