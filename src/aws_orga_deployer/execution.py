"""Execute the steps of a deployment package."""

import logging
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime
from threading import Event, Lock, Thread
from typing import Any, Dict

from aws_orga_deployer import config, utils
from aws_orga_deployer.engines import ENGINES
from aws_orga_deployer.package import Package, graph
from aws_orga_deployer.package.store import ModuleAccountRegionKey

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class SubprocessError(Exception):
    """Exception to raise if an error occurs when running subprocesses."""


class Executor:
    """Class that is used to execute the steps of a deployment package using
    the modules.

    Attributes:
        package: Current package.
        nb_times_sigint: Number of times CTRL+C was pressed.
        stop_workers: Event object used to inform worker threads that they must
            stop after completing the current step.
        send_sigint: Event object used to inform worker threads that they must
            send a SIGINT signal to their subprocesses to quit gracefully.
        send_sigint: Event object used to inform worker threads that they must
            send a SIGTERM signal to their subprocesses to force quit.
        aws_temp_credentials: Store AWS temporary credentials retrieved for each
            IAM role and when they were obtained. Avoid to do an AssumeRole for
            every step.
        lock_aws_temp_credentials: Lock object to avoid multiple threads to
            retrieve AWS temporary credentials at the same time.
        lock_next: Lock object to avoid multiple threads to retrieve the next
            step at the same time.
        engines_cache_dir: Path to the folder that contains engines cache
        deployments_cache_dir: Path to the folder that contains deployments cache
        root_logs_dir: Root path to the logs of this run
    """

    package: Package
    nb_times_sigint: int
    stop_workers: Event
    send_sigint: Event
    send_sigterm: Event
    aws_temp_credentials: Dict[str, Any]
    lock_aws_temp_credentials: Lock
    lock_next: Lock
    engines_cache_dir: Dict[str, str]
    deployments_cache_dir: str
    root_logs_dir: str

    def __init__(self, package: Package) -> None:
        self.package = package
        self.nb_times_sigint = 0
        self.stop_workers = Event()
        self.send_sigint = Event()
        self.send_sigterm = Event()
        self.aws_temp_credentials = {}
        self.lock_aws_temp_credentials = Lock()
        self.lock_next = Lock()
        self._create_temp_folders()

    def _create_temp_folders(self) -> None:
        """Create the temporary folders in the local disk to store cache files
        and logs.
        """
        cache_dir = os.path.join(config.CLI["temp_dir"], "cache")
        # Create one cache folder for each engine (cache/engines/engine)
        self.engines_cache_dir = {}
        for engine in ENGINES:
            engine_dir = os.path.join(cache_dir, "engines", engine)
            self.engines_cache_dir[engine] = engine_dir
            if not os.path.isdir(engine_dir):
                os.makedirs(engine_dir)
        # Delete deployment cache folders if exist (cache/deployments)
        self.deployments_cache_dir = os.path.join(cache_dir, "deployments")
        if os.path.exists(self.deployments_cache_dir):
            shutil.rmtree(self.deployments_cache_dir)
        # Evaluate if deployment cache must persist after this run
        self.delete_deployment_cache = (
            config.CLI.get("keep_deployment_cache", False) is False
        )
        # Create the logs folder (outputs/YYYYMMDD-HHMMSS)
        current_date = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        self.root_logs_dir = os.path.join(config.CLI["temp_dir"], "logs", current_date)
        if not os.path.isdir(self.root_logs_dir):
            os.makedirs(self.root_logs_dir)

    def run(self) -> None:
        """Function to call to launch the execution of steps."""
        # Catch SIGINT signals to be able to stop gracefully the processing of
        # steps
        signal.signal(signal.SIGINT, self._catch_sigint)
        # Launch concurrent threads to execute the steps
        nb_threads = config.PACKAGE.get(
            "ConcurrentWorkers", config.DEFAULT_CONCURRENT_WORKERS
        )
        threads = []
        for worker_id in range(nb_threads):
            thread = Thread(
                target=self.worker,
                daemon=True,
                name=f"Worker{worker_id}",
            )
            thread.start()
            threads.append(thread)
        # Wait until the threads complete
        for thread in threads:
            thread.join()
        # Save the current state store before exiting
        self.package.save()
        # Delete the deployments cache root folder if needed
        if self.delete_deployment_cache:
            shutil.rmtree(self.deployments_cache_dir, ignore_errors=True)
        # Stop catching SIGINT signals
        signal.signal(signal.SIGINT, Executor._stop_catching_sigint)

    def worker(self) -> None:
        """Main function executed by concurrent workers."""

        LOGGER.debug("Starting worker")
        while True:
            # Stop the worker is `stop_workers` is set
            if self.stop_workers.is_set():
                break
            # Get the next deployment to process. Use a lock to avoid
            # multiple workers to update the package graph at the same time
            # pylint: disable=bare-except
            # pylint: disable=broad-exception-caught
            try:
                with self.lock_next:
                    key, action, nb_attempts, max_attempts = self.package.next()
                    LOGGER.info(
                        "%s Starting to %s (Attempt %s/%s)",
                        key,
                        action,
                        nb_attempts,
                        max_attempts,
                    )
            # Wait one second if there are still pending deployments but they
            # are all waiting for dependencies to complete
            except graph.NoProcessableStep:
                time.sleep(1)
                continue
            # Stop the worker if there are no more pending deployments
            except graph.NoMorePendingStep:
                break
            # Stop the worker if `next` failed
            except:
                LOGGER.error(
                    "Worker failed to get the next deployment to process",
                    exc_info=config.CLI["debug"],
                )
                break
            # If the requested command is "update-hash", attempt to update the
            # module hash and move to the next deployment to process
            if config.CLI["command"] == "update-hash":
                hash_changed = self.package.update_hash(key)
                if hash_changed:
                    LOGGER.info("%s Updated the value of the module hash", key)
                else:
                    LOGGER.info("%s No action needed", key)
                continue
            # Use this variable to indicate where the step fails in the
            # detailed error logs
            section_that_failed = "other"
            # Determine the name of the deployment cache
            deployment_cache_dir = os.path.join(
                self.deployments_cache_dir, key.module, key.account_id, key.region
            )
            # Catch any exceptions to prevent the worker thread from being
            # interrupted if the module fails
            try:
                # Measure the step execution time
                start_time = datetime.now()
                # Create the deployment cache dir
                os.makedirs(deployment_cache_dir)
                # If the action is "create" or "update", the variables that are
                # passed are those expected in the target date. If the action is
                # "delete", the variables that are passed are those in the
                # current state.
                if action in ("create", "update"):
                    variables = self.package.target[key].variables
                else:
                    variables = self.package.current[key].variables
                # Call `prepare` to prepare input files to subprocesses, and
                # retrieve a list of commands to execute in subprocesses
                try:
                    module_config = self.package.get_module_config(key)
                    LOGGER.debug("%s Executing prepare", key)
                    commands = config.MODULES[key.module].prepare(
                        key=key,
                        command=config.CLI["command"],
                        action=action,
                        variables=variables,
                        module_config=module_config,
                        deployment_cache_dir=deployment_cache_dir,
                        engine_cache_dir=self.engines_cache_dir[
                            config.MODULES[key.module].engine
                        ],
                    )
                except:
                    section_that_failed = "prepare"
                    raise
                # Execute subprocesses
                for command in commands:
                    env = os.environ.copy()
                    env.update(command.env)
                    # Assume an IAM role if needed and add AWS temporary
                    # credentials to the environment variables
                    iam_role = module_config.get("AssumeRole")
                    if command.assume_role and not iam_role is None:
                        self._add_aws_temp_credentials(env, iam_role)
                    # Execute the subprocess
                    LOGGER.debug("%s Executing subprocess '%s'", key, command.name)
                    LOGGER.debug("%s Command: %s", key, " ".join(command.args))
                    LOGGER.debug("%s Cwd: %s", key, command.cwd)
                    try:
                        # pylint: disable=subprocess-popen-preexec-fn
                        # pylint: disable=consider-using-with
                        # Need to catch SIGINT signals to exit gracefully
                        process = subprocess.Popen(
                            command.args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            env=env,
                            cwd=command.cwd,
                            shell=False,
                            start_new_session=True,
                        )
                        sent_sigint = False
                        sent_sigterm = False
                        while True:
                            # Check every second if a signal SIGINT or SIGTERM must
                            # be sent to be the subprocess. Wait for the subprocess
                            # to exit after sending the signal
                            try:
                                stdout, stderr = process.communicate(timeout=0.1)
                                # Write the subprocess logs
                                self._write_subprocess_logs(
                                    key,
                                    command.name,
                                    nb_attempts,
                                    "stdout.log",
                                    stdout.decode(),
                                )
                                self._write_subprocess_logs(
                                    key,
                                    command.name,
                                    nb_attempts,
                                    "stderr.log",
                                    stderr.decode(),
                                )
                                # Write stdout to a file if needed:
                                if not command.stdout_file is None:
                                    with open(command.stdout_file, "wb") as stream:
                                        stream.write(stdout)
                                # The subprocess must return an exit code of 0
                                if process.returncode != 0:
                                    section_that_failed = f"subprocess '{command.name}'"
                                    raise SubprocessError("Exit code is not 0")
                                # Interrupt the step if SIGINT or SIGTERM was
                                # pressed
                                if sent_sigint or sent_sigterm:
                                    section_that_failed = f"subprocess '{command.name}'"
                                    raise SubprocessError("Subprocess interrupted")
                                # Exit the loop if the subprocess has completed
                                break
                            except subprocess.TimeoutExpired:
                                if self.send_sigint.is_set() and not sent_sigint:
                                    process.send_signal(signal.SIGINT)
                                    sent_sigint = True
                                if self.send_sigterm.is_set() and not sent_sigterm:
                                    process.send_signal(signal.SIGTERM)
                                    sent_sigterm = True
                    except:
                        section_that_failed = f"subprocess '{command.name}'"
                        raise
                # Execute the post-process function to parse outputs from the
                # subprocesses
                try:
                    LOGGER.debug("%s Executing postprocess", key)
                    outcome = config.MODULES[key.module].postprocess(
                        key=key,
                        command=config.CLI["command"],
                        action=action,
                        module_config=module_config,
                        deployment_cache_dir=deployment_cache_dir,
                    )
                except:
                    section_that_failed = "postprocess"
                    raise
                # Complete the step if no exception was raised
                self.package.complete(
                    key,
                    made_changes=outcome.made_changes,
                    result=outcome.result,
                    detailed_results=outcome.detailed_results,
                    outputs=outcome.outputs,
                )
                LOGGER.info("%s Completed - %s", key, outcome.result)
                # Display the step execution time
                stop_time = datetime.now()
                elapsed_ms = (stop_time - start_time).total_seconds()
                LOGGER.debug("%s Execution time: %.3f seconds", key, elapsed_ms)
            # Catch any exceptions and mark the step as failed
            except Exception as err:
                LOGGER.error(
                    "%s Failed. See logs for details", key, exc_info=config.CLI["debug"]
                )
                self.package.fail(
                    key,
                    result="Failed",
                    detailed_results={
                        "FailedSection": section_that_failed,
                        "ErrorMessage": str(err),
                    },
                )
            # Delete the deployment cache for this deployment if needed
            finally:
                if self.delete_deployment_cache:
                    shutil.rmtree(deployment_cache_dir, ignore_errors=True)

    def _add_aws_temp_credentials(self, env: Dict[str, Any], iam_role: str) -> None:
        """Add AWS temporary credentials as environment variables to the dict
        `env`.

        Args:
            env (dict): Dictionary to which environment variables are added
            iam_role (str): ARN of the IAM role to assume
        """
        with self.lock_aws_temp_credentials:
            credentials = None
            # If AWS temporary credentials was created for this role less than
            # `CACHE_AWS_TEMP_CREDS` seconds ago, reuse the credentials
            if iam_role in self.aws_temp_credentials:
                created_at = self.aws_temp_credentials[iam_role]["CreatedAt"]
                created_since = (datetime.utcnow() - created_at).total_seconds()
                if created_since < config.CACHE_AWS_TEMP_CREDS:
                    credentials = self.aws_temp_credentials[iam_role]["Credentials"]
            # Otherwise, assume the role and add AWS temporary credentials to the
            # cache
            if credentials is None:
                credentials = utils.get_aws_temp_credentials(iam_role)
                self.aws_temp_credentials[iam_role] = {
                    "CreatedAt": datetime.utcnow(),
                    "Credentials": credentials,
                }
            # Add environment variables
            env["AWS_ACCESS_KEY_ID"] = credentials["AccessKeyId"]
            env["AWS_SECRET_ACCESS_KEY"] = credentials["SecretAccessKey"]
            env["AWS_SESSION_TOKEN"] = credentials["SessionToken"]

    def _write_subprocess_logs(
        self,
        key: ModuleAccountRegionKey,
        name_command: str,
        nb_attempts: int,
        filename: str,
        content: str,
    ) -> None:
        """Append subprocess logs to the local disk.

        Args:
            root_logs_dir: Root path of the folder that stores logs for this run
            key: Step key
            name_command: Name of the subprocess
            nb_attempts: Current attempt number
            filename: Name of the file to which logs must be appended
            content: Logs to append
        """
        # Create the folder for the log of this module deployment if it does not
        # exist
        log_path = os.path.join(
            self.root_logs_dir, key.module, key.account_id, key.region
        )
        if not os.path.isdir(log_path):
            os.makedirs(log_path)
        # Write the logs
        log_file = os.path.join(log_path, filename)
        with open(log_file, "a", encoding="utf-8") as stream:
            stream.write("################################\n")
            stream.write(f"# Subprocess '{name_command}'' - Attempt #{nb_attempts}\n")
            stream.write("################################\n")
            stream.write(content)
            stream.write("\n")

    # pylint: disable=unused-argument
    # The arguments `sig` and `frame` are mandatory but unused

    def _catch_sigint(self, sig, frame) -> None:
        """Catch SIGINT signals while workers are running. The first time
        CTRL+C is pressed, workers must stop after completing their current
        step. The second time, workers must be send a SIGINT signal to the
        running subprocess and wait for a graceful exit. The third time,
        workers must send a SIGTERM and wait subprocesses to exit. The fourth
        time, a KeyboardInterrupt exception is raised to interrupt this
        program.
        """

        self.nb_times_sigint += 1
        if self.nb_times_sigint == 1:
            self.stop_workers.set()
            LOGGER.info("Interrupted - Waiting for current deployments to complete")
        elif self.nb_times_sigint == 2:
            self.send_sigint.set()
            LOGGER.info("Interrupted - Sending SIGINT to subprocesses")
        elif self.nb_times_sigint == 3:
            self.send_sigterm.set()
            LOGGER.info("Interrupted - Sending SIGTERM to subprocesses")
        elif self.nb_times_sigint == 4:
            self.package.save()
            LOGGER.info("Interrupted - Forcing deployments to abort")
            raise KeyboardInterrupt
        else:
            raise KeyboardInterrupt

    @staticmethod
    def _stop_catching_sigint(sig, frame) -> None:
        """Stop catching SIGINT."""
        raise KeyboardInterrupt
