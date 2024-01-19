"""Test the module `aws_orga_deployer.package.store`."""

# COMPLETED
import time
import unittest

from moto import mock_s3

from aws_orga_deployer.package import store
from tests import mock


class TestModuleAccountRegionKey(unittest.TestCase):
    """Test the class ModuleAccountRegionKey."""

    def test_init(self):
        """Check equivalence."""
        key1 = store.ModuleAccountRegionKey("Module", "AccountId", "Region")
        key2 = store.ModuleAccountRegionKey("Module", "AccountId", "Region")
        self.assertEqual(key1, key2)

    def test_init_dict(self):
        """Check equivalence when loaded from a dict."""
        key1 = store.ModuleAccountRegionKey("Module", "AccountId", "Region")
        key2 = store.ModuleAccountRegionKey({
            "Module": "Module",
            "AccountId": "AccountId",
            "Region": "Region",
        })
        self.assertEqual(key1, key2)

    def test_export(self):
        """Check the export."""
        key = store.ModuleAccountRegionKey("Module", "AccountId", "Region")
        self.assertDictEqual(
            key.to_dict(),
            {"Module": "Module", "AccountId": "AccountId", "Region": "Region"},
        )


class TestPackageStateStore(unittest.TestCase):
    """Test the class PackageStateStore."""

    def setUp(self):
        """Mock a S3 bucket."""
        mock.mock_package_config()
        # Enable persistent mocking
        self.mock_s3 = mock_s3()
        self.mock_s3.start()
        # Create a fake S3 bucket to store the organisation cache
        mock.create_fake_bucket()
        # Create test key and value
        self.key = store.ModuleAccountRegionKey("m1", "a1", "r1")
        self.value = store.CurrentDeploymentDetails(
            variables={"key": "value"},
            var_from_outputs={"key": "value"},
            dependencies=["item"],
            outputs={"key": "value"},
            module_hash="hash",
            last_changed_time="time",
        )

    def tearDown(self):
        """Disable mocking."""
        self.mock_s3.stop()

    def test_create_save_reload(self):
        """Check that the package state is saved and retrieved from S3."""
        # Create a `PackageStateStore` object, edit its value and save to S3.
        state = store.CurrentStateStore()
        self.assertFalse(state.save())
        state[self.key] = self.value
        self.assertTrue(state.save())
        # Reload the package state from S3 and check that the value was
        # correctly saved to S3
        state_reloaded = store.CurrentStateStore()
        self.assertIn(self.key, state_reloaded.keys())
        self.assertIn(self.value, state_reloaded.values())
        # Stop the auto-save or it might continue to write to S3 after this test
        # has completed
        state.stop()
        state_reloaded.stop()

    def test_save_automatically_enabled(self):
        """Check that the package state is automatically saved to S3."""
        # Create a `PackageStateStore` object that saves to S3 every 0.1
        # seconds, and update its value
        state = store.CurrentStateStore(period=0.1)
        state[self.key] = self.value
        time.sleep(0.5)
        # Reload the package state from S3 and check that the value was
        # correctly saved to S3
        state_reloaded = store.CurrentStateStore()
        self.assertIn(self.key, state_reloaded.keys())
        self.assertIn(self.value, state_reloaded.values())
        # Stop the auto-save or it might continue to write to S3 after this test
        # has completed
        state.stop()
        state_reloaded.stop()

    def test_save_automatically_disabled(self):
        """Check the behavior when the periodic saving is disabled."""
        # Create a `PackageStateStore` object with periodic saving disabled
        state = store.CurrentStateStore(period=0)
        state[self.key] = self.value
        time.sleep(0.5)
        # Reload the package state from S3 and check that the value was not
        # save to S3
        state_reloaded = store.CurrentStateStore()
        self.assertNotIn(self.key, state_reloaded.keys())
        self.assertNotIn(self.value, state_reloaded.values())
