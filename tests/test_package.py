"""Test the module `aws_orga_deployer.package.__init__`."""

import time
import unittest
from unittest.mock import patch

from moto import mock_organizations, mock_s3, mock_sts

from aws_orga_deployer import modules
from aws_orga_deployer.orga import OrgaParser
from aws_orga_deployer.package import Package, PackageError, graph, store
from tests import mock
from tests.mock import mock_others
from tests.utils import update_cli_filters


class TestPackage(unittest.TestCase):
    """Test the class Package. At the end of each test, make sure to stop the
    auto-save of the current state store for each Package instance, or the
    daemon thread may continue to write to S3 after the test has completed,
    creating an inconsistent state.
    """

    @mock_sts
    @mock_others
    def setUp(self):
        """Create mock resources and an OrgaParser object that must exist for
        all tests.
        """
        mock.mock_cli_arguments(package_filename="package1.yaml")
        # Enable mocking for S3 and Organizations in all tests without having
        # to add declarators to each test function
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
        """Disable mocking for S3 and Organizations."""
        self.mock_s3.stop()
        self.mock_organizations.stop()

    def test_complete(self):
        """Complete a series of tests reflecting standard usage."""
        package1 = Package()
        package1.full_init(self.orga)
        # Check the number of module deployments in the target state. There
        # should be "python1" modules in all accounts in us-east-1 only, and
        # "terraform1" in all accounts except master in all enabled regions
        nb_expected = len(self.orga.accounts) + (
            len(mock.ENABLED_REGIONS) * (len(self.orga.accounts) - 1)
        )
        self.assertEqual(len(package1.target), nb_expected)
        # Check the result of `analyze_changes`. It should return that there
        # are pending changes
        has_pending_changes = package1.analyze_changes()
        self.assertTrue(has_pending_changes)
        # Check the result of `export_changes`. It should contain the same
        # number of items in `result["PendingChanges"]["Create"]`
        export = package1.export_changes()
        self.assertEqual(len(export["PendingChanges"]["Create"]), nb_expected)
        # Check the content of one specific item in the target state
        key = store.ModuleAccountRegionKey(
            "terraform1", self.fake_orga.account_a_id, mock.ENABLED_REGIONS[0]
        )
        self.assertIn(key, package1.target)
        self.assertIn("var1", package1.target[key].variables)
        self.assertIn("terraform1", package1.target[key].variables["varGlobal"])
        # Check the module configuration and that the value of `AssumeRole`
        # matches the account ID
        module_config = package1.get_module_config(key)
        self.assertEqual(
            module_config["AssumeRole"],
            f"arn:aws:iam::{self.fake_orga.account_a_id}:role/Admin",
        )
        # Retrieve the next step to process and check that it matches a step
        # for "python1" module in the us-east-1 region
        key, action, nb_attempts, max_attempts = package1.next()
        self.assertEqual(key.module, "python1")
        self.assertEqual(key.region, "us-east-1")
        self.assertEqual(action, "create")
        self.assertEqual(nb_attempts, 1)
        self.assertEqual(max_attempts, 2)
        # Complete the step
        package1.complete(
            key,
            made_changes=True,
            result="Summary",
            detailed_results={"keyDetail": "valueDetail"},
            outputs={"outputPython1": "valueOutput"},
        )
        # Check that the current state contains one item for the step that was
        # just completed and check its value
        self.assertIn(key, package1.current)
        self.assertEqual(
            package1.current[key].outputs["outputPython1"],
            "valueOutput",
        )
        # Check the results export. There should be one completed create step
        export = package1.export_results()
        self.assertEqual(len(export["Completed"]["Create"]), 1)
        self.assertEqual(export["Completed"]["Create"][0]["ResultedInChanges"], True)
        # Reload the package and check that the current state is loaded from S3
        package1.save()
        package2 = Package()
        package2.full_init(self.orga)
        self.assertIn(key, package2.current)

    def test_update(self):
        """Test the class Package with deployments to update."""
        package1 = Package()
        package1.full_init(self.orga)
        # Complete a deployment and change the value of the variables in the
        # current state to simulate that an update is needed
        key, _, _, _ = package1.next()
        package1.complete(key, made_changes=True, result="Summary")
        package1.current[key].variables["varPython1"] = "old_value"
        package1.save()
        # Reload the package and check that there is one pending update to
        # make
        package2 = Package()
        package2.full_init(self.orga)
        export = package2.export_changes()
        self.assertEqual(len(export["PendingChanges"]["Update"]), 1)
        # Complete all deployments
        try:
            while True:
                key, _, _, _ = package2.next()
                package2.complete(key, made_changes=True, result="Summary")
        except graph.NoMorePendingStep:
            pass
        # Reload the package and check that there are pending changes
        package2.save()
        package3 = Package()
        package3.full_init(self.orga)
        self.assertFalse(package3.analyze_changes())

    # Change the command to preview
    def test_update_preview_mode(self):
        """Test the class Package with deployments to update."""
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"command": "preview"}),
        ):
            package1 = Package()
            package1.full_init(self.orga)
            # Complete all deployments
            try:
                while True:
                    key, _, _, _ = package1.next()
                    package1.complete(key, made_changes=True, result="Summary")
            except graph.NoMorePendingStep:
                pass
            # Reload the package and check that there is are still pending
            # deployments because it was preview mode
            package1.save()
            package2 = Package()
            package2.full_init(self.orga)
            self.assertTrue(package2.analyze_changes())

    def test_update_hash(self):
        """Test the `update_hash` function."""
        package1 = Package()
        package1.full_init(self.orga)
        # Retrieve the next step and change the value of the module hash in the
        # current state to simulate that an update is needed because the value
        # of the module hash differs
        key, _, _, _ = package1.next()
        package1.complete(key, made_changes=True, result="Summary")
        package1.current[key].module_hash = "fake_hash"
        # Retrieve another step and change the value of the variables
        key, _, _, _ = package1.next()
        package1.complete(key, made_changes=True, result="Summary")
        package1.current[key].variables = {"var2": "value2"}
        # Reload the package and execute the `update_hash` function for all
        # steps, until there are no more steps to process
        package1.save()
        package2 = Package()
        package2.full_init(self.orga)
        try:
            while True:
                key, _, _, _ = package2.next()
                package2.update_hash(key)
        except graph.NoMorePendingStep:
            pass
        # Check that there two updates in the results (the other steps are
        # pending creation)
        export = package2.export_results()
        self.assertEqual(len(export["Completed"]["Update"]), 2)
        # Check that one has resulted in changes (module hash changed) and the
        # other no (change in variables)
        made_changes = set(
            item["ResultedInChanges"] for item in export["Completed"]["Update"]
        )
        self.assertEqual(made_changes, set([True, False]))
        # Reload the package and there should be one step with no changes to
        # be made (module hash changed) and one with update (variables updated)
        package2.save()
        package3 = Package()
        package3.full_init(self.orga)
        export = package3.export_changes()
        self.assertEqual(len(export["NoChanges"]), 1)
        self.assertEqual(len(export["PendingChanges"]["Update"]), 1)

    def test_destroy(self):
        """Test the class Package with deployments to destroy."""
        package1 = Package()
        package1.full_init(self.orga)
        # Retrieve a step to process and complete the deployment
        key, _, _, _ = package1.next()
        package1.complete(key, made_changes=True, result="Summary")
        # Reload the package and remove the deployments in the target state to
        # simulate that a resource exists in the current state, but not in the
        # target state and it must be destroyed
        package1.save()
        package2 = Package()
        for module_block in package2.package["Modules"].values():
            module_block["Deployments"] = []
        package2.full_init(self.orga)
        # Check that there are deployments to destroy
        result = package2.export_changes()
        self.assertEqual(len(result["PendingChanges"]["Destroy"]), 1)
        # Complete the deployment
        key, _, _, _ = package2.next()
        package2.complete(key, made_changes=True, result="Summary")
        # Reload the package and check that there are no deployments to destroy
        package2.save()
        package3 = Package()
        package3.full_init(self.orga)
        result = package3.export_changes()
        self.assertNotIn("Delete", result["PendingChanges"])

    def test_nonexistent_module(self):
        """Test the class Package with deployments in the current state for
        which there is no module block in the package definition file.
        """
        package1 = Package()
        package1.full_init(self.orga)
        # Retrieve a step to process and complete the deployment
        key, _, _, _ = package1.next()
        package1.complete(key, made_changes=True, result="Summary")
        package1.save()
        # Reload the package and remove all the module blocks. It should raise
        # a PackageError exception
        package2 = Package()
        package2.package["Modules"] = {}
        with self.assertRaises(PackageError):
            package2.full_init(self.orga)

    # Add a filter to include only the "us-east-1" region
    def test_cli_filters(self):
        """Test the class Package with CLI filters."""
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"include_regions": ["us-east-1"]}),
        ):
            package1 = Package()
            package1.full_init(self.orga)
            # Check the number of pending changes that are not skipped. There
            # should be "python1" in all accounts in us-east-1 only, and
            # "terraform1" in all accounts except master in us-east-1 only
            self.assertTrue(package1.analyze_changes())
            nb_pending = len(self.orga.accounts) * 2 - 1
            export = package1.export_changes()
            self.assertEqual(len(export["PendingChanges"]["Create"]), nb_pending)
            # Check that the number of steps returned matches this number
            nb_steps_returned = 0
            try:
                while True:
                    key, _, _, _ = package1.next()
                    package1.complete(key, made_changes=True, result="Summary")
                    nb_steps_returned += 1
            except graph.NoMorePendingStep:
                pass
            self.assertEqual(nb_steps_returned, nb_pending)

    def test_nonexistent_account(self):
        """Test the behavior with current deployments in AWS accounts that
        are not active anymore.
        """
        package1 = Package()
        package1.full_init(self.orga)
        # Add a fake deployment to the current state
        fake_key = store.ModuleAccountRegionKey(
            "terraform1", "098765432109", "us-east-1"
        )
        package1.current[fake_key] = store.CurrentDeploymentDetails(
            variables={},
            var_from_outputs={},
            dependencies=[],
            module_hash="fake_hash",
            outputs={},
            last_changed_time="",
        )
        package1.save()
        # Reload the package and check that there should be one pending but
        # skipped destroy change, because the fake AWS account ID doesn't
        # belong to the list of active accounts in the organization
        package2 = Package()
        package2.full_init(self.orga)
        export = package2.export_changes()
        self.assertEqual(len(export["PendingButSkippedChanges"]["Destroy"]), 1)

    def test_fail(self):
        """Test the behavior with a failed deployment."""
        # Add a filter to include only the account ID "123456789012" (master)
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"include_account_ids": [self.fake_orga.account_a_id]}),
        ):
            package1 = Package()
            package1.full_init(self.orga)
            # Retrieve the next step and mark it as failed. It should return a step
            # for module "python1"
            key1, _, nb_attempts, _ = package1.next()
            self.assertEqual(nb_attempts, 1)
            package1.fail(key1, result="Failed")
            # Try again, it should raise NoProcessableStep because this step must
            # be completed before other steps can be processed and
            # `DelayBeforeRetrying` is step to 1 second.
            with self.assertRaises(graph.NoProcessableStep):
                package1.next()
            # Retry after 1 seconds
            time.sleep(1)
            key2, _, nb_attempts, _ = package1.next()
            self.assertEqual(key1, key2)
            self.assertEqual(nb_attempts, 2)
            package1.complete(key2, made_changes=True, result="Completed")
            # Retrieve the next step, it should corresponds to a deployment
            # for "terraform1" module
            key, _, _, _ = package1.next()
            self.assertEqual(key.module, "terraform1")

    def test_conditional_update_1(self):
        """Test the behavior with conditional updates and output values that
        don't change.
        """
        package1 = Package()
        package1.full_init(self.orga)
        # Mark all steps as completed
        try:
            while True:
                key, _, _, _ = package1.next()
                package1.complete(
                    key,
                    made_changes=True,
                    result="Summary",
                    outputs={"outputPython1": "value"},
                )
        except graph.NoMorePendingStep:
            pass
        # Change the value of the module hash in the current state to simulate
        # the need to update a deployment
        key = store.ModuleAccountRegionKey(
            "python1", self.fake_orga.account_a_id, "us-east-1"
        )
        package1.current[key].module_hash = "fake_hash"
        # Reload the package
        package1.save()
        package2 = Package()
        package2.full_init(self.orga)
        # Check that there is one update, and one conditional update because
        # the module "terraform1" depends on the outputs of "python1"
        export = package2.export_changes()
        self.assertEqual(len(export["PendingChanges"]["Update"]), 1)
        self.assertEqual(
            len(export["PendingChanges"]["ConditionalUpdate"]),
            len(mock.ENABLED_REGIONS),
        )
        # Mark the first step for "python1" as completed and don't change the
        # value of the outputs
        key, _, _, _ = package2.next()
        package2.complete(
            key,
            made_changes=True,
            result="Summary",
            outputs={"outputPython1": "value"},
        )
        # There should be no other step because the value of outputs have not
        # changed
        with self.assertRaises(graph.NoMorePendingStep):
            package2.next()
        # Check that there are multiple completed conditional updates in the
        # results and none has result in changes
        export = package2.export_results()
        self.assertGreater(len(export["Completed"]["ConditionalUpdate"]), 1)
        self.assertNotIn(
            True,
            [
                item["ResultedInChanges"]
                for item in export["Completed"]["ConditionalUpdate"]
            ],
        )

    def test_conditional_update_2(self):
        """Test the behavior with conditional updates and output values that
        change.
        """
        package1 = Package()
        package1.full_init(self.orga)
        # Mark all steps as completed
        try:
            while True:
                key, _, _, _ = package1.next()
                package1.complete(
                    key,
                    made_changes=True,
                    result="Summary",
                    outputs={"outputPython1": "value"},
                )
        except graph.NoMorePendingStep:
            pass
        # Change the value of the module hash in the current state to simulate
        # the need to update a deployment
        key = store.ModuleAccountRegionKey(
            "python1", self.fake_orga.account_a_id, "us-east-1"
        )
        package1.current[key].module_hash = "fake_hash"
        # Reload the package
        package1.save()
        package2 = Package()
        package2.full_init(self.orga)
        # Check that there is one update, and one conditional update before
        # the module "terraform1" depends on the outputs of "python1"
        export = package2.export_changes()
        self.assertEqual(len(export["PendingChanges"]["Update"]), 1)
        self.assertEqual(
            len(export["PendingChanges"]["ConditionalUpdate"]),
            len(mock.ENABLED_REGIONS),
        )
        # Mark the first step for "python1" as completed and change the value
        # of the output
        key, _, _, _ = package2.next()
        package2.complete(
            key,
            made_changes=True,
            result="Summary",
            outputs={"outputPython1": "new_value"},
        )
        # Check that the value of the current state is correct
        self.assertEqual(package2.current[key].outputs["outputPython1"], "new_value")
        # The next step should be "update" because the outputs value changed,
        # and that the value of the variable matches the value of the
        # ascendant output
        key, action, _, _ = package2.next()
        self.assertEqual(action, "update")
        self.assertEqual(package2.target[key].variables["varTerraform1"], "new_value")
        package2.complete(key, made_changes=True, result="Summary")
        # Check that there is one completed conditional update in the results
        # and it resulted in changes
        export = package2.export_results()
        self.assertEqual(len(export["Completed"]["ConditionalUpdate"]), 1)
        self.assertTrue(
            export["Completed"]["ConditionalUpdate"][0]["ResultedInChanges"]
        )

    def test_no_update_needed(self):
        """Test the behavior when there are no updates to make."""
        package1 = Package()
        package1.full_init(self.orga)
        # Mark all steps as completed
        try:
            while True:
                key, _, _, _ = package1.next()
                package1.complete(key, made_changes=True, result="Summary")
        except graph.NoMorePendingStep:
            pass
        # Reload the package and check that there are no pending changes
        package1.save()
        package2 = Package()
        package2.full_init(self.orga)
        self.assertFalse(package2.analyze_changes())

    # Set the CLI argument `--force-update`
    def test_force_update(self):
        """Test the behavior when there are no changes to make but we force
        updates using CLI argument.
        """
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"force_update": True}),
        ):
            package1 = Package()
            package1.full_init(self.orga)
            # Mark all steps as completed
            try:
                while True:
                    key, _, _, _ = package1.next()
                    package1.complete(key, made_changes=True, result="Summary")
            except graph.NoMorePendingStep:
                pass
            # Reload the package and check that there are pending changes
            package1.save()
            package2 = Package()
            package2.full_init(self.orga)
            self.assertTrue(package2.analyze_changes())

    # Set the CLI command to "preview"
    def test_preview_with_dependencies(self):
        """Test the behavior in "preview" mode where deployments have changes
        to be made, but they dependent on other deployments also with
        pending changes.
        """
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"command": "preview"}),
        ):
            package1 = Package()
            package1.full_init(self.orga)
            # Mark all steps as completed
            try:
                while True:
                    key, _, _, _ = package1.next()
                    package1.complete(key, made_changes=True, result="Summary")
            except graph.NoMorePendingStep:
                pass
            # Check that there is at least one deployment that failed, because
            # changes to resources cannot be previewed when dependencies have
            # pending changes
            export = package1.export_results()
            self.assertGreaterEqual(len(export["Failed"]["Create"]), 1)

    def test_missing_dependencies_not_ignored_1(self):
        """Test the behavior with dependencies that don't exist with the attribute
        `IgnoreIfNotExists` not set.
        """
        # Use the package file "package3.yaml" for this test
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"package_file": mock.get_test_path("package3.yaml")}),
        ):
            package = Package()
            with self.assertRaises(graph.GraphError):
                package.full_init(self.orga)

    def test_missing_dependencies_not_ignored_2(self):
        """Test the behavior with dependencies that don't exist with the attribute
        `IgnoreIfNotExists` not set for all dependencies.
        """
        # Use the package file "package3.yaml" for this test
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"package_file": mock.get_test_path("package3.yaml")}),
        ):
            package = Package()
            # Modify the package content to set "IgnoreIfNotExists" for the
            # first deployment block only
            deployments = package.package["Modules"]["terraform1"]["Deployments"]
            deployments[0]["Dependencies"][0]["IgnoreIfNotExists"] = True
            with self.assertRaises(graph.GraphError):
                package.full_init(self.orga)

    def test_missing_dependencies_ignored(self):
        """Test the behavior with dependencies that don't exist with the attribute
        `IgnoreIfNotExists` set to True for all dependencies.
        """
        # Use the package file "package3.yaml" for this test
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"package_file": mock.get_test_path("package3.yaml")}),
        ):
            package = Package()
            # Modify the package content to set "IgnoreIfNotExists" for both
            # deployment blocks
            deployments = package.package["Modules"]["terraform1"]["Deployments"]
            deployments[0]["Dependencies"][0]["IgnoreIfNotExists"] = True
            deployments[1]["VariablesFromOutputs"]["var1"]["IgnoreIfNotExists"] = True
            package.full_init(self.orga)
            # Mark all steps as completed
            try:
                while True:
                    key, _, _, _ = package.next()
                    package.complete(key, made_changes=True, result="Summary")
            except graph.NoMorePendingStep:
                pass
            # Check that the value of the "var1" for the module "terraform1"
            # is still equal to "value1" as the "VariablesFromOutputs"
            # dependency does not exist
            key = store.ModuleAccountRegionKey(
                "terraform1", "123456789012", "us-east-2"
            )
            self.assertEqual(package.current[key].variables["var1"], "value1")

    def test_package_save_state_enabled(self):
        """Test the behavior with the argument `save-state-every-seconds` = 1."""
        with patch(
            "aws_orga_deployer.config.CLI",
            update_cli_filters({"save_state_every_seconds": 1}),
        ):
            package1 = Package()
            package1.full_init(self.orga)
            # Mark all steps as completed
            try:
                while True:
                    key, _, _, _ = package1.next()
                    package1.complete(key, made_changes=True, result="Summary")
            except graph.NoMorePendingStep:
                pass
            time.sleep(2)
            package2 = Package()
            package2.full_init(self.orga)
            export = package2.export_changes()
            self.assertNotIn("PendingChanges", export.keys())
            package1.save(stop_autosave=True)
            package2.save(stop_autosave=True)

    def test_package_save_state_disabled(self):
        """Test the behavior without the argument `save-state-every-seconds`."""
        package1 = Package()
        package1.full_init(self.orga)
        # Mark all steps as completed
        try:
            while True:
                key, _, _, _ = package1.next()
                package1.complete(key, made_changes=True, result="Summary")
        except graph.NoMorePendingStep:
            pass
        # First attempt without saving
        time.sleep(2)
        package2 = Package()
        package2.full_init(self.orga)
        export = package2.export_changes()
        self.assertIn("PendingChanges", export.keys())
        # Second attempt after saving
        package1.save()
        package3 = Package()
        package3.full_init(self.orga)
        export = package3.export_changes()
        self.assertNotIn("PendingChanges", export.keys())

    def test_remove_orphans(self):
        """Test that remove_orphans removes module deployments for accounts
        that no longer exist in the organization.
        """
        package1 = Package()
        package1.full_init(self.orga)
        # Add a fake deployment to the current state
        fake_key = store.ModuleAccountRegionKey(
            "terraform1", "098765432109", "us-east-1"
        )
        package1.current[fake_key] = store.CurrentDeploymentDetails(
            variables={},
            var_from_outputs={},
            dependencies=[],
            module_hash="fake_hash",
            outputs={},
            last_changed_time="",
        )
        package1.save()
        # Reload the package and remove orphans
        package2 = Package()
        package2.full_init(self.orga)
        orphans_removed = package2.remove_orphans()
        self.assertIn(fake_key.to_dict(), orphans_removed)
        # Reload the package and check that there are no module deployments
        # to destroy
        package3 = Package()
        package3.full_init(self.orga)
        export = package3.export_changes()
        self.assertNotIn("PendingButSkippedChanges", export.keys())


class TestInvalidPackage(unittest.TestCase):
    """Test the class Package with invalid package definition files."""

    @mock_s3
    def test_invalid_package_1(self):
        """Test the behavior with an empty package definition file."""
        # Create a fake bucket
        mock.create_fake_bucket()
        # Change the location of the package definition file
        mock.mock_cli_arguments(package_filename="invalid-package1.yaml")
        with self.assertRaises(PackageError):
            Package()

    @mock_s3
    def test_invalid_package_2(self):
        """Test the behavior with an invalid package definition file."""
        # Create a fake bucket
        mock.create_fake_bucket()
        # Change the location of the package definition file
        mock.mock_cli_arguments(package_filename="invalid-package2.yaml")
        with self.assertRaises(PackageError):
            Package()
