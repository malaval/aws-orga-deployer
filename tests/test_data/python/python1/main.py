"""This Python module does nothing but return fake results."""

import boto3


def main(
    module,
    account_id,
    region,
    command,
    action,
    variables,
    module_config,
    module_dir,
    deployment_cache_dir,
    engine_cache_dir,
):
    # Retrieve the current account ID
    endpoint_url = module_config["EndpointUrls"]["sts"]
    client = boto3.client("sts", endpoint_url=endpoint_url, region_name="eu-west-1")
    account_id = client.get_caller_identity()["Account"]
    # Return the account ID in the detailed results
    if command == "preview":
        return True, "Result", {"AccountId": account_id}, None
    return True, "Result", {"AccountId": account_id}, {"output": "value"}
