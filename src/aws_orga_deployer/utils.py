"""General utility functions."""

# COMPLETED
import json
import logging
import queue
from threading import Thread
from typing import Any, Callable, Dict, List, Optional

import boto3
from botocore.config import Config
from botocore.session import Session

from aws_orga_deployer import config

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def get_aws_temp_credentials(
    iam_role: str,
    sts_session: Optional[Session] = None,
) -> Dict[str, str]:
    """Assume an IAM role and return AWS temporary credentials.

    Args:
        iam_role: ARN of the IAM role to assume.
        sts_session: boto3 Session to use for the STS call. Defaut is None to
            use a new session with current AWS credentials.

    Returns:
        dict: With `AccessKeyId`, `SecretAccessKey` and `SessionToken`
            attributes.
    """
    if sts_session is None:
        sts_client = boto3.client("sts")
    else:
        sts_client = sts_session.client("sts")
    LOGGER.debug("Assuming the IAM role %s", iam_role)
    response = sts_client.assume_role(
        RoleArn=iam_role, RoleSessionName="aws-orga-deployer"
    )
    return response["Credentials"]


def get_aws_session(
    iam_role: Optional[str] = None,
    sts_session: Optional[Session] = None,
) -> Session:
    """Assume an IAM role if needed and return a boto3 Session object.

    Args:
        iam_role: ARN of the IAM role to assume. Defaut is None to use current
            AWS credentials.
        sts_session: boto3 Session to use for the STS call. Defaut is None to
            use a new session with current AWS credentials.

    Returns:
        Session: boto3 Session.
    """
    # If a role must be assumed
    if iam_role:
        credentials = get_aws_temp_credentials(iam_role, sts_session)
        return boto3.session.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
    # If current AWS credentials are used
    return boto3.session.Session()


def get_aws_client(session: Session, *args: Any, **kwargs: Any) -> Any:
    """Return a boto3 Client with retry configuration.

    Args:
        session: boto3 Session to use.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        boto3 Client object.
    """
    boto_config = Config(retries={"max_attempts": 10, "mode": "standard"})
    return session.client(*args, config=boto_config, **kwargs)


class PropagatingThread(Thread):
    """Thread object that raises exception in the parent thread."""

    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=broad-exception-caught

    def run(self) -> None:
        self.exc = None
        try:
            self.ret = self._target(*self._args, **self._kwargs)
        except BaseException as exception:
            self.exc = exception

    def join(self, timeout: Optional[float] = None) -> Any:
        super().join(timeout)
        if self.exc:
            raise self.exc
        return self.ret


def exec_multithread(items: List[Any], func: Callable, concurrency: int) -> None:
    """Execute a function for each item of a list using concurrent threads.

    Args:
        items: List of items to process.
        func: Function to use to process each item.
        concurrency: Number of concurrent threads.
    """
    items_queue: queue.Queue = queue.Queue()
    # Populate the queue
    for item in items:
        items_queue.put(item)

    # Create a wrapper function that pulls the queue
    def wrapper():
        while True:
            try:
                item = items_queue.get(block=False)
                func(item)
            except queue.Empty:
                break
            items_queue.task_done()

    # Launch concurrent threads
    threads = []
    for _ in range(concurrency):
        thread = PropagatingThread(target=wrapper, daemon=True)
        thread.start()
        threads.append(thread)
    # Wait until the threads complete
    for thread in threads:
        thread.join()


def get_s3_key(object_path: str) -> str:
    """Prepends the S3 prefix to the object path and returns the result.

    Args:
        object_path: Object path

    Returns:
        S3Prefix concatenated with object path.
    """
    return config.PACKAGE.get("S3Prefix", "") + object_path


class FileNotExists(Exception):
    """Exception raised if the S3 object does not exist when using
    `load_dict_from_s3`.
    """


def load_json_from_s3(object_path: str) -> Dict:
    """Load a JSON file from S3 and return a dict.

    Args:
        object_path: Object path in the dedicated S3 prefix.

    Returns:
        Dictionary containing the JSON file.

    Raises:
        FileNotExists: If the object does not exist in S3.
    """
    bucket = config.PACKAGE["S3Bucket"]
    key = get_s3_key(object_path)
    client = get_aws_client(
        get_aws_session(), "s3", region_name=config.PACKAGE["S3Region"]
    )
    try:
        LOGGER.debug("Reading the S3 object at s3://%s/%s", bucket, key)
        response = client.get_object(Bucket=bucket, Key=key)
        content_bytes = response["Body"].read()
        return json.loads(content_bytes.decode())
    except client.exceptions.NoSuchKey as err:
        raise FileNotExists from err


def write_dict_to_s3(content: Dict, object_path: str) -> None:
    """Write a dict to Amazon S3 as a JSON file.

    Args:
        content: Content to wroite.
        object_path: Object path in the dedicated S3 prefix.
    """
    content_bytes = json.dumps(content, indent=4).encode()
    bucket = config.PACKAGE["S3Bucket"]
    key = get_s3_key(object_path)
    client = get_aws_client(
        get_aws_session(), "s3", region_name=config.PACKAGE["S3Region"]
    )
    LOGGER.debug("Writing the S3 object at s3://%s/%s", bucket, key)
    client.put_object(
        Body=content_bytes, Bucket=bucket, Key=key, ContentType="application/json"
    )


def write_output_json(input_dict: Dict, description: str) -> None:
    """Write the input dictionary as a JSON file to the local disk.

    Args:
        input_dict: Input content
        description: Description of the file to print in the logs
    """
    LOGGER.info("Exporting %s to %s", description, config.CLI["output_file"])
    with open(config.CLI["output_file"], "w", encoding="utf-8") as stream:
        content = json.dumps(input_dict, indent=4)
        stream.write(content)
