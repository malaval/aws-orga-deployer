"""Test the module `aws_orga_deployer.package.graph`."""
# COMPLETED
import time
import unittest

from aws_orga_deployer.package import graph, store


class TestDeploymentGraph(unittest.TestCase):
    """Test the class DeploymentGraph."""

    def test_missing_dependency(self):
        """Check that a GraphError exception is raised if a dependency does not
        exist.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        dep.add_step(step1, action="create", skip=False)
        with self.assertRaises(graph.GraphError):
            dep.add_dependency(step2, step1, is_var=False)

    def test_ignored_missing_dependency(self):
        """Check that a GraphError exception is not raised if a dependency does
        not exist when the argument `ignore_if_not_exists` is True.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        dep.add_step(step1, action="create", skip=False)
        dep.add_dependency(step2, step1, is_var=False, ignore_if_not_exists=True)

    def test_loop(self):
        """Check that a GraphError exception is raised if the package contains
        circular dependencies.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        step3 = store.ModuleAccountRegionKey("m3", "a1", "r1")
        dep.add_step(step1, action="create", skip=False)
        dep.add_step(step2, action="create", skip=False)
        dep.add_step(step3, action="create", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.add_dependency(step2, step3, is_var=False)
        dep.add_dependency(step3, step1, is_var=False)
        with self.assertRaises(graph.GraphError):
            dep.validate()

    def test_ancestors_not_created(self):
        """Check that deployments that depend on other deployments can only be
        created if their ancestors have been created.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        dep.add_step(step1, action="create", skip=True)
        dep.add_step(step2, action="create", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        with self.assertRaises(graph.GraphError):
            dep.validate()

    def test_descendants_not_deleted(self):
        """Check that eployments on which other deployments depend can only be
        deleted if their descendants have been deleted.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        dep.add_step(step1, action="destroy", skip=False)
        dep.add_step(step2, action="destroy", skip=True)
        dep.add_dependency(step1, step2, is_var=False)
        with self.assertRaises(graph.GraphError):
            dep.validate()

    def test_selfloop(self):
        """Check that a GraphError exception is raised if the package contains
        self-loops.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        dep.add_step(step1, action="create", skip=False)
        dep.add_dependency(step1, step1, is_var=True)
        with self.assertRaises(graph.GraphError):
            dep.validate()

    def test_conditional_update(self):
        """Check that the update status propagates correctly with
        `VariablesFromOutputs` dependencies.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        step3 = store.ModuleAccountRegionKey("m3", "a1", "r1")
        dep.add_step(step1, action="update", skip=False)
        dep.add_step(step2, action="none", skip=False)
        dep.add_step(step3, action="none", skip=False)
        dep.add_dependency(step1, step2, is_var=True)
        dep.add_dependency(step2, step3, is_var=True)
        dep.validate()
        # We expect the status of step2 and step3 to become "conditional-update"
        # because their variables depend on step1 outputs, which may change
        for _, details in dep.list_steps_with_details():
            self.assertIn(details.action, ("update", "conditional-update"))
        # Check that the steps are correctly returned
        self.assertEqual(dep.next(), step1)
        dep.complete(step1)
        self.assertEqual(dep.next(), step2)
        dep.complete(step2)
        self.assertEqual(dep.next(), step3)
        dep.complete(step3)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_create(self):
        """Check the behavior of a valid graph with create actions only."""
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        step3 = store.ModuleAccountRegionKey("m3", "a1", "r1")
        dep.add_step(step1, action="create", skip=False)
        dep.add_step(step2, action="create", skip=False)
        dep.add_step(step3, action="create", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.add_dependency(step2, step3, is_var=False)
        dep.validate()
        self.assertTrue(dep.has_ascendants_with_changes(step2))
        self.assertEqual(dep.next(), step1)
        with self.assertRaises(graph.NoProcessableStep):
            dep.next()
        dep.complete(step1)
        self.assertEqual(dep.next(), step2)
        dep.complete(step2)
        self.assertEqual(dep.next(), step3)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_create_2(self):
        """Another check the behavior of a valid graph with create actions only."""
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        step3 = store.ModuleAccountRegionKey("m3", "a1", "r1")
        dep.add_step(step1, action="create", skip=False)
        dep.add_step(step2, action="create", skip=False)
        dep.add_step(step3, action="create", skip=False)
        dep.add_dependency(step1, step3, is_var=False)
        dep.add_dependency(step2, step3, is_var=False)
        dep.validate()
        self.assertIn(dep.next(), (step1, step2))
        self.assertIn(dep.next(), (step1, step2))
        with self.assertRaises(graph.NoProcessableStep):
            dep.next()
        dep.complete(step1)
        dep.complete(step2)
        self.assertEqual(dep.next(), step3)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_delete(self):
        """Check the behavior of a valid graph with delete actions only."""
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        step3 = store.ModuleAccountRegionKey("m3", "a1", "r1")
        dep.add_step(step1, action="destroy", skip=False)
        dep.add_step(step2, action="destroy", skip=False)
        dep.add_step(step3, action="destroy", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.add_dependency(step2, step3, is_var=False)
        dep.validate()
        self.assertEqual(dep.next(), step3)
        dep.complete(step3)
        self.assertEqual(dep.next(), step2)
        dep.complete(step2)
        self.assertEqual(dep.next(), step1)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_create_delete(self):
        """Check the behavior of a valid graph with create and delete actions."""
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        step3 = store.ModuleAccountRegionKey("m3", "a1", "r1")
        step4 = store.ModuleAccountRegionKey("m4", "a1", "r1")
        dep.add_step(step1, action="update", skip=False)
        dep.add_step(step2, action="update", skip=False)
        dep.add_step(step3, action="destroy", skip=False)
        dep.add_step(step4, action="destroy", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.add_dependency(step2, step3, is_var=False)
        dep.add_dependency(step3, step4, is_var=False)
        dep.validate()
        self.assertEqual(dep.next(), step4)
        dep.complete(step4)
        self.assertEqual(dep.next(), step3)
        dep.complete(step3)
        self.assertEqual(dep.next(), step1)
        dep.complete(step1)
        self.assertEqual(dep.next(), step2)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_create_with_skipped(self):
        """Check the behavior of a valid graph with skipped steps. If there is
        no action to make for step1, and step2 is skipped, only step3 should be
        returned."""
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        step3 = store.ModuleAccountRegionKey("m3", "a1", "r1")
        dep.add_step(step1, action="none", skip=False)
        dep.add_step(step2, action="update", skip=True)
        dep.add_step(step3, action="update", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.add_dependency(step2, step3, is_var=False)
        dep.validate()
        self.assertEqual(dep.next(), step3)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_failed(self):
        """Check the behavior of a valid graph with failed steps: If step1
        fails, step2 and step3 should also fail."""
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        step3 = store.ModuleAccountRegionKey("m3", "a1", "r1")
        dep.add_step(step1, action="create", skip=False)
        dep.add_step(step2, action="create", skip=False)
        dep.add_step(step3, action="create", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.add_dependency(step2, step3, is_var=False)
        dep.validate()
        self.assertEqual(dep.next(), step1)
        dep.fail(step1)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_with_failed_then_successful_retries(self):
        """Check the behavior of a valid graph with a step that fails at the
        first attempt, and succeeds at the second.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        dep.add_step(step1, action="create", skip=False, max_attempts=2)
        dep.add_step(step2, action="create", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.validate()
        self.assertEqual(dep.next(), step1)
        dep.fail(step1)
        self.assertEqual(dep.next(), step1)
        dep.complete(step1)
        self.assertEqual(dep.next(), step2)
        dep.complete(step2)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_with_failed_retries(self):
        """Check the behavior of a valid graph with a step that fails during
        all attempts.
        """
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        dep.add_step(step1, action="create", skip=False, max_attempts=2)
        dep.add_step(step2, action="create", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.validate()
        self.assertEqual(dep.next(), step1)
        dep.fail(step1)
        self.assertEqual(dep.next(), step1)
        dep.fail(step1)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_with_delay_between_retries(self):
        """Check the behavior of a valid graph with a delay between retries."""
        dep = graph.DeploymentGraph()
        step1 = store.ModuleAccountRegionKey("m1", "a1", "r1")
        step2 = store.ModuleAccountRegionKey("m2", "a1", "r1")
        dep.add_step(step1, action="create", skip=False, max_attempts=2, delay=1)
        dep.add_step(step2, action="create", skip=False)
        dep.add_dependency(step1, step2, is_var=False)
        dep.validate()
        self.assertEqual(dep.next(), step1)
        dep.fail(step1)
        with self.assertRaises(graph.NoProcessableStep):
            dep.next()
        time.sleep(1)
        self.assertEqual(dep.next(), step1)
        dep.complete(step1)
        self.assertEqual(dep.next(), step2)
        dep.complete(step2)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()

    def test_long_graph(self):
        """Check the behavior of with a valid long graph: Let us assume that
        there are 20 regions, 10 accounts and 3 modules.
        - module1 is deployed in all accounts in region1
        - module2 is deployed in all accounts and all regions, and depends on
          module 1
        - module3 is deployed in all accounts and all regions, and depends on
          module2.
        """
        dep = graph.DeploymentGraph()
        # Create steps and dependencies
        for n_account in range(10):
            step1 = store.ModuleAccountRegionKey("m1", f"a{n_account}", "r1")
            dep.add_step(step1, action="create", skip=False)
            for n_region in range(20):
                step2 = store.ModuleAccountRegionKey(
                    "m2", f"a{n_account}", f"r{n_region}"
                )
                dep.add_step(step2, action="create", skip=False)
                dep.add_dependency(step1, step2, is_var=False)
                step3 = store.ModuleAccountRegionKey(
                    "m3", f"a{n_account}", f"r{n_region}"
                )
                dep.add_step(step3, action="create", skip=False)
                dep.add_dependency(step2, step3, is_var=False)
        dep.validate()
        # There should be 10 deployments for module1 and 200 for module2 and
        # module3 to complete
        for _ in range(2 * 10 * 20 + 1 * 10):
            current_step = dep.next()
            dep.complete(current_step)
        with self.assertRaises(graph.NoMorePendingStep):
            dep.next()
