"""Module to represent the execution of a package as a graph, with nodes
representing the steps and each step corresponding to a module deployment,
and the edges representing dependencies between steps.
"""

# COMPLETED
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import networkx as nx

from aws_orga_deployer.package.store import ModuleAccountRegionKey

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class GraphError(Exception):
    """Exception raised when the deployment graph is invalid."""


class NoMorePendingStep(Exception):
    """Exception raised when `next` has no steps to return because all pending
    steps in a graph have been processed.
    """


class NoProcessableStep(Exception):
    """Exception raised when `next` has no steps to return because all remaining
    steps need to wait for their dependencies to complete.
    """


class StepDetails:
    """Store details about a graph step.

    Attributes:
        action: Action to make for this step. Can be "none" (no action
            to make), "create" (deployment to create), "update" (deployment
            to update), "conditional-update" (deployment to update only if the
            values of outputs on which the deployment depends change), "destroy"
            (deployment to destroy).
        skip: True if the step is skipped due to CLI arguments, or because no
            action is needed.
        status: Current step status. Can be "pending", "skipped", "ongoing",
            "completed" or "failed".
        nb_attempts: Number of times this step has been attempted.
        max_attempts: Number of times this step should be attempted before
            it is marked as "failed".
        delay: Delay in seconds to wait before retrying this step.
        wait_until: Must wait until `wait_until` because attempting to process
            this step.
        result: One-line summary of the result.
        detailed_results: Optional detailed results, such as the list of
            resources created, updated or deleted.
        made_changes: True if the step resulted in changes made or to be made
    """

    action: str
    skip: bool
    status: str
    nb_attempts: int
    max_attempts: int
    delay: int
    wait_until: datetime
    result: str
    detailed_results: Optional[Dict]
    made_changes: bool

    def __init__(self, action: str, skip: bool, max_attempts: int, delay: int) -> None:
        self.action = action
        self.skip = skip
        self.status = "pending"
        self.nb_attempts = 0
        self.max_attempts = max_attempts
        self.delay = delay
        self.wait_until = datetime.utcnow()
        self.result = ""
        self.detailed_results = None
        self.made_changes = False


class DeploymentGraph:
    """Class that represents the deployment steps, their dependencies and
    status.
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    def list_steps(self) -> List[ModuleAccountRegionKey]:
        """Returns the list of steps in the deployment graph.

        Returns:
            List of keys.
        """
        return self._graph.nodes

    def list_steps_with_details(
        self,
    ) -> List[Tuple[ModuleAccountRegionKey, StepDetails]]:
        """Returns the list of steps in the deployment graph and their details.

        Returns:
            List of tuples (key, details).
        """
        return self._graph.nodes(data="details")

    def get_step_details(self, key: ModuleAccountRegionKey) -> StepDetails:
        """Return the details for a given step.

        Args:
            key: Step key

        Returns:
            Step details
        """
        return self._graph.nodes[key]["details"]

    def has_ascendants_with_changes(self, key: ModuleAccountRegionKey) -> bool:
        """Return True if the step has ascendant dependencies on steps with
        pending changes to be made.

        Args:
            key: Step key

        Returns:
            True if at least one ascendant step has changes to be made.
        """
        for ascendant in self._graph.predecessors(key):
            details = self._graph.nodes[ascendant]["details"]
            if details.skip is False and (
                details.action in ("create", "destroy")
                or (
                    details.action in ("update", "conditional-update")
                    and details.made_changes is True
                )
            ):
                return True
        return False

    def add_step(
        self,
        key: ModuleAccountRegionKey,
        action: str,
        skip: bool,
        max_attempts: int = 1,
        delay: int = 0,
    ) -> None:
        """Add a new step in the graph, which corresponds to a module
        deployment. Refers to the attributes of `StepDetails` for description.

        Args:
            key: Step key
            action: Action to be made
            skip: True if the step should be skipped
            max_attempts: Maximum number of attemps for this step
            delay: Number of steps to wait before retrying
        """
        details = StepDetails(action, skip, max_attempts, delay)
        self._graph.add_node(key, details=details)

    def add_dependency(
        self,
        from_key: ModuleAccountRegionKey,
        to_key: ModuleAccountRegionKey,
        is_var: bool,
        ignore_if_not_exists: bool = False,
    ) -> None:
        """Add a new edge in the graph, which corresponds to a dependency
        between steps.

        Args:
            from_key: Dependency of the module deployment.
            to_key: Module deployment
            is_var (str): True if the dependency is of type `VariablesFromOutputs`.
            ignore_if_not_exists: Ignore if the dependent deployment does not
                exist if set to True. Otherwise, raise an exception.

        Raises:
            GraphError: If the dependency does not exist in the graph, unless
                the action is `delete` because we don't need to wait for the
                dependency to be deleted if it doesn't exist, or if
                `ignore_if_not_exists` is True.
        """
        to_details = self._graph.nodes[to_key]["details"]
        if not from_key in self._graph.nodes:
            if to_details.action == "destroy" or ignore_if_not_exists is True:
                return
            raise GraphError(f"{to_key} depends on {from_key} which does not exist")
        self._graph.add_edge(from_key, to_key, is_var=is_var)

    def validate(self) -> None:
        """Validate the graph and make initial changes."""
        self._check_for_loops()
        self._check_for_uncreatable_deployments()
        self._check_for_undeletable_deployments()
        self._propagate_conditional_update()
        self._set_status_skipped()
        LOGGER.debug(
            "The deployment graph is valid and contains %s steps and %s dependencies",
            len(self._graph.nodes),
            len(self._graph.edges),
        )

    def _check_for_loops(self) -> None:
        """Check that there are no loops in the graph."""
        if not nx.is_directed_acyclic_graph(self._graph):
            # Identify cycles in the graph
            cycles = []
            for cycle in list(nx.simple_cycles(self._graph)):
                cycles.append(">".join([str(node) for node in cycle]))
            raise GraphError(
                f"The package contains circular dependencies: {' and '.join(cycles)}"
            )

    def _check_for_uncreatable_deployments(self) -> None:
        """Steps that depend on other deployments can only be created if
        their ancestors have been created.
        """
        for to_key, to_details in self._graph.nodes(data="details"):
            if not (to_details.action == "create" and to_details.skip is False):
                continue
            for from_key in self._graph.predecessors(to_key):
                from_details = self._graph.nodes[from_key]["details"]
                if from_details.action == "destroy" and from_details.skip is False:
                    raise GraphError(
                        f"{to_key} must be created after {from_key} which will be"
                        " deleted during this run"
                    )
                if from_details.action == "create" and from_details.skip is True:
                    raise GraphError(
                        f"{to_key} must be created after {from_key} which has not yet"
                        " been created and will not be created during this run"
                    )

    def _check_for_undeletable_deployments(self) -> None:
        """Deployments on which other deployments depend can only be deleted if
        their descendants have been deleted."""
        for from_key, from_details in self._graph.nodes(data="details"):
            if not (from_details.action == "destroy" and from_details.skip is False):
                continue
            for to_key in self._graph.successors(from_key):
                to_details = self._graph.nodes[to_key]["details"]
                if to_details.action == "create" and to_details.skip is True:
                    return
                if to_details.action == "destroy" and to_details.skip is False:
                    return
                raise GraphError(
                    f"{from_key} must be deleted after {to_key} which has not yet"
                    " been deleted and will not be deleted during this run"
                )

    def _propagate_conditional_update(self) -> None:
        """When a deployment A depends on the output values of a deployment B,
        updating B may require updating A if the output values change. Repeat
        until propagation is completed.
        """
        while True:
            changes_made = False
            for from_key, to_key, is_var in self._graph.edges(data="is_var"):
                if is_var:
                    from_details = self._graph.nodes[from_key]["details"]
                    to_details = self._graph.nodes[to_key]["details"]
                    if (
                        from_details.action in ("update", "conditional-update")
                        and to_details.action == "none"
                    ):
                        to_details.action = "conditional-update"
                        changes_made = True
            if not changes_made:
                break

    def _set_status_skipped(self) -> None:
        """Change the status of steps where no actions are needed or steps to
        skip.
        """
        for _, details in self._graph.nodes(data="details"):
            if details.action == "none" or details.skip is True:
                details.status = "skipped"

    def next(self) -> ModuleAccountRegionKey:
        """Return the next step to process.

        Returns:
            The next step key to process.

        Raises:
            aws_orga_deployer.package.graph.NoProcessableStep
            aws_orga_deployer.package.graph.NoMorePendingStep
        """

        def step_is_waiting(details: StepDetails) -> bool:
            """Return True if `wait_until` is in the future."""
            return details.wait_until > datetime.utcnow()

        def mark_as_ongoing(details: StepDetails) -> None:
            """Change the status to "ongoing" and add one to the number of
            attempts.
            """
            details.status = "ongoing"
            details.nb_attempts += 1

        def mark_as_failed(key: ModuleAccountRegionKey, details: StepDetails) -> None:
            """Change the status to "failed" because one of the dependencies
            failed.
            """
            details.status = "failed"
            details.result = "Failed because at least one dependency failed"
            LOGGER.error("%s Failed because at least one dependency failed", key)

        # The topological sort returns the list of steps in the order of which
        # they must be processed (dependencies first)
        path = list(nx.topological_sort(self._graph))
        # We start with delete operations, from the end of the path because
        # deployments must be deleted before their dependencies are deleted
        for key in reversed(path):
            details = self._graph.nodes[key]["details"]
            # Skip if the step is still waiting after a failed attempt
            if step_is_waiting(details):
                continue
            # If a deployment must be deleted
            if details.action == "destroy" and details.status == "pending":
                # If at least one descendant failed, change the status to
                # failed
                if any(
                    self._graph.nodes[descendant_key]["details"].status == "failed"
                    for descendant_key in self._graph.successors(key)
                ):
                    mark_as_failed(key, details)
                # If all descendants have completed, change the status to
                # ongoing and return the node key
                if all(
                    self._graph.nodes[descendant_key]["details"].status
                    in ("completed", "skipped")
                    for descendant_key in self._graph.successors(key)
                ):
                    mark_as_ongoing(details)
                    return key
        # We continue with all create and update operations, from the beginning
        # of the path, if no delete operation was returned
        for key in path:
            details = self._graph.nodes[key]["details"]
            # Skip if the step is still waiting after a failed attempt
            if step_is_waiting(details):
                continue
            # If a node must be created or updated
            if (
                details.action in ("create", "update", "conditional-update")
                and details.status == "pending"
            ):
                # If at least one ancestor failed, the status is changed to
                # failed
                if any(
                    self._graph.nodes[ancestor_key]["details"].status == "failed"
                    for ancestor_key in self._graph.predecessors(key)
                ):
                    mark_as_failed(key, details)
                # If all ancestors have completed or are skipped, the node can
                # be processed
                if all(
                    self._graph.nodes[ancestor_key]["details"].status
                    in ("completed", "skipped")
                    for ancestor_key in self._graph.predecessors(key)
                ):
                    mark_as_ongoing(details)
                    return key
        # Raise NoProcessableStep if there are still pending steps to process
        # but their dependencies must complete first
        if any(
            details.status == "pending"
            for _, details in self._graph.nodes(data="details")
        ):
            raise NoProcessableStep
        # Raise NoMorePendingStep if there is no more steps to process
        raise NoMorePendingStep

    def complete(
        self,
        key: ModuleAccountRegionKey,
        made_changes: bool = False,
        result: str = "",
        detailed_results: Optional[Dict] = None,
    ) -> None:
        """Change the status of a node to "completed" and set the value
        of the result.

        Args:
            key: Step key
            made_changes: True if the step resulted in changes made or to be made
            result: One-line summary of the result. Default to empty.
            detailed_results: Dict with detailed results. Default to None.
        """
        details = self._graph.nodes[key]["details"]
        details.status = "completed"
        details.made_changes = made_changes
        details.result = result
        details.detailed_results = detailed_results

    def fail(
        self,
        key: ModuleAccountRegionKey,
        result: str = "",
        detailed_results: Optional[Dict] = None,
    ) -> None:
        """Change the status of a node to "failed" if no further retries should
        be attempted and set the value of the result.

        Args:
            key: Step key.
            result: One-line summary of the result. Default to empty.
            detailed_results: Dict with detailed results. Default to None.
        """
        details = self._graph.nodes[key]["details"]
        # If the number of maximum attempts is not reached, set the status
        # to "pending"
        details.result = result
        details.detailed_results = detailed_results
        if details.nb_attempts < details.max_attempts:
            details.status = "pending"
            details.wait_until = datetime.utcnow() + timedelta(seconds=details.delay)
        else:
            details.status = "failed"
