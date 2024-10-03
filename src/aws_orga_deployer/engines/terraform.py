"""Engine for Terraform modules."""

import json
import shutil
from os import path
from typing import Any, Dict, List

from aws_orga_deployer import config, utils
from aws_orga_deployer.engines import base
from aws_orga_deployer.package.store import ModuleAccountRegionKey


class Engine(base.BaseEngine):
    """Engine for Terraform modules."""

    engine = "terraform"
    default_included_patterns = ["*.tf"]
    default_excluded_patterns = []

    def validate_module_config(self, module_config: Dict[str, Any]) -> None:
        """Validate the content of the module configuration.

        Args:
            module_config: Module configuration.

        Raises:
            AssertionError
        """
        super().validate_module_config(module_config)
        if "TerraformExecutable" in module_config:
            assert isinstance(
                module_config["TerraformExecutable"], str
            ), "TerraformExecutable must be a string"

    def prepare(
        self,
        key: ModuleAccountRegionKey,
        command: str,
        action: str,
        variables: Dict[str, Any],
        module_config: Dict[str, Any],
        deployment_cache_dir: str,
        engine_cache_dir: str,
    ) -> List[base.StepCommand]:
        """Prepare Terraform files in the deployment cache directory and return
        a list of Terraform commands to execute in subprocesses.

        Args:
            key: Step key to execute.
            command: CLI command requested ("preview" or "deploy").
            action: Action to be made ("create", "update" or "destroy").
            variables: Input variables.
            module_config: Module configuration.
            deployment_cache_dir: Path to the module deployment cache directory.
            engine_cache_dir: Path to the engine cache directory (common to all
                modules for this engine).

        Returns:
            List of commands to execute in subprocesses.
        """
        # If the action is "create" or "update", copy the Terraform templates
        # that exist in the module directory to the deployment cache directory,
        # and prepare a file `terraform.tfvars.json`. If the action is "delete",
        # the directory doesn't contain any Terraform which means that the
        # target state must not contain any resources.
        if action in ("create", "update"):
            # The existing directory must not exist, or `copytree` fails with
            # Python 3.7
            shutil.rmtree(deployment_cache_dir, ignore_errors=True)
            shutil.copytree(self.module_dir, deployment_cache_dir)
            # Create the file `terraform.tfvars.json`
            var_filename = path.join(deployment_cache_dir, "terraform.tfvars.json")
            with open(var_filename, "w", encoding="utf-8") as stream:
                json.dump(variables, stream, indent=4)
        if action in ("destroy"):
            # If the module directory contains a file `override.tf`, copy it
            # to the deployment cache directory so that custom provider
            # configuration is preserved for destroy operation
            override_filename = path.join(self.module_dir, "override.tf")
            if path.exists(override_filename):
                shutil.copy(override_filename, deployment_cache_dir)
        # Create a file `aws_orga_deployer.tf` that contains the configuration
        # of the AWS provider and of the S3 backend
        tf_filename = path.join(deployment_cache_dir, "aws_orga_deployer.tf")
        with open(tf_filename, "w", encoding="utf-8") as stream:
            stream.write('provider "aws" {\n')
            stream.write(f'  region = "{key.region}"\n')
            # If an IAM role must be assumed in the target AWS account, it must
            # be assumed by the provider, so that the S3 backend has permissions
            # in the current execution account to write in the package state
            # bucket.
            if not module_config.get("AssumeRole") is None:
                stream.write("  assume_role {\n")
                stream.write(f'    role_arn = "{module_config["AssumeRole"]}"\n')
                stream.write('    session_name = "aws-orga-deployer"\n')
                stream.write("  }\n")
            # Add custom endpoints for the AWS provider if needed
            if "EndpointUrls" in module_config:
                stream.write("  endpoints {\n")
                for service, url in module_config["EndpointUrls"].items():
                    stream.write(f'    {service} = "{url}"\n')
                stream.write("  }\n")
            stream.write("}\n")
            stream.write("terraform {\n")
            stream.write('  backend "s3" {\n')
            stream.write(f'    bucket = "{config.PACKAGE["S3Bucket"]}"\n')
            stream.write(f'    region = "{config.PACKAGE["S3Region"]}"\n')
            s3_key = utils.get_s3_key(
                f"terraform/{key.module}/{key.account_id}/{key.region}/terraform.tfstate"
            )
            stream.write(f'    key = "{s3_key}"\n')
            # Add custom endpoints for S3, STS and IAM for the S3 backend
            if "EndpointUrls" in module_config:
                for service, url in module_config["EndpointUrls"].items():
                    if service == "s3":
                        stream.write(f'    endpoint = "{url}"\n')
                        stream.write("    force_path_style = true\n")

                    elif service == "sts":
                        stream.write(f'    sts_endpoint = "{url}"\n')
                    elif service == "iam":
                        stream.write(f'    iam_endpoint = "{url}"\n')
            stream.write("  }\n")
            stream.write("}\n")
        # Get the path to the Terraform executable
        terraform_exec = "terraform"
        if not module_config.get("TerraformExecutable") is None:
            terraform_exec = module_config["TerraformExecutable"]
        # Set arguments and environment variables that are common to all
        # Terraform commands
        common_args = ["-no-color"]
        common_env = {
            "TF_PLUGIN_CACHE_DIR": engine_cache_dir,
            "TF_PLUGIN_CACHE_MAY_BREAK_DEPENDENCY_LOCK_FILE": "true",
        }
        # `terraform init` is needed whether the command or the action
        commands = [
            base.StepCommand(
                name="init",
                args=[terraform_exec, "init", *common_args],
                cwd=deployment_cache_dir,
                assume_role=False,
                env=common_env,
            )
        ]
        # The following commands are needed for both "preview" and "apply"
        # commands
        commands += [
            base.StepCommand(
                name="plan",
                args=[terraform_exec, "plan", "-out=tfplan", *common_args],
                cwd=deployment_cache_dir,
                assume_role=False,
                env=common_env,
            ),
            # The output of the following command must be stored in a file so
            # that the `postprocess` is able to identify the resources to
            # add, change or delete
            base.StepCommand(
                name="get plan in JSON",
                args=[terraform_exec, "show", "-json", "tfplan", *common_args],
                cwd=deployment_cache_dir,
                assume_role=False,
                env=common_env,
                stdout_file=path.join(deployment_cache_dir, "plan.json"),
            ),
        ]
        # The following commands are only run if command is "apply" to apply
        # the plan and get outputs
        if command == "apply":
            commands += [
                base.StepCommand(
                    name="apply plan",
                    args=[
                        terraform_exec,
                        "apply",
                        "-auto-approve",
                        *common_args,
                        "tfplan",
                    ],
                    cwd=deployment_cache_dir,
                    assume_role=False,
                    env=common_env,
                )
            ]
            # If the action is not "destroy", get the outputs from the Terraform
            # state. The output must be stored in a file, so that `postprocess`
            # can read the outputs.
            if action in ("create", "update"):
                commands += [
                    base.StepCommand(
                        name="get outputs",
                        args=[terraform_exec, "output", "-json", *common_args],
                        cwd=deployment_cache_dir,
                        assume_role=False,
                        env=common_env,
                        stdout_file=path.join(deployment_cache_dir, "output.json"),
                    ),
                ]
        return commands

    def postprocess(
        self,
        key: ModuleAccountRegionKey,
        command: str,
        action: str,
        module_config: Dict[str, Any],
        deployment_cache_dir: str,
    ) -> base.StepOutcome:
        """Reads the file `output.json` created by the "wrapper" function and
        returns the outputs.

        Args:
            key: Step key to execute.
            command: CLI command requested.
            action: Action to be made ("create", "update", "destroy").
            module_config: Module configuration.
            deployment_cache_dir: Path to the module deployment cache directory.

        Returns:
            Outcome of the step.
        """
        # Identify the resources to add, change or delete from the Terraform
        # plan
        res_add = []
        res_change = []
        res_delete = []
        plan_file = path.join(deployment_cache_dir, "plan.json")
        with open(plan_file, "r", encoding="utf-8") as stream:
            content = json.load(stream)
            for change in content.get("resource_changes", []):
                actions = change["change"]["actions"]
                if actions == ["create"]:
                    res_add.append(change["address"])
                elif actions == ["delete"]:
                    res_delete.append(change["address"])
                # Actions ["delete", "create"] or ["create", "delete"]
                # correspond to "update" because the resource is deleted and
                # recreated
                elif actions in (
                    ["update"],
                    ["delete", "create"],
                    ["create", "delete"],
                ):
                    res_change.append(change["address"])
        # If the command is "preview", the outputs must be named "to add", "to
        # change" or to "to delete" and no outputs is needed
        if command == "preview":
            return base.StepOutcome(
                made_changes=len(res_add + res_change + res_delete) > 0,
                result=(
                    f"{len(res_add)} resources to add, "
                    f"{len(res_change)} to change, "
                    f"{len(res_delete)} to delete"
                ),
                detailed_results={
                    "ResourcesToAdd": res_add,
                    "ResourcesToChange": res_change,
                    "ResourcesToDelete": res_delete,
                },
            )
        # If the command is "apply", the outcomes must be named "added",
        # "changed" or "deleted" and outputs must be provided if action is
        # "create" or "update"
        if action in ("create", "update"):
            output_file = path.join(deployment_cache_dir, "output.json")
            with open(output_file, "r", encoding="utf-8") as stream:
                content = json.load(stream)
                outputs = {key: value["value"] for key, value in content.items()}
        else:
            outputs = None
        return base.StepOutcome(
            made_changes=len(res_add + res_change + res_delete) > 0,
            result=(
                f"{len(res_add)} resources added, "
                f"{len(res_change)} changed, "
                f"{len(res_delete)} deleted"
            ),
            detailed_results={
                "ResourcesAdded": res_add,
                "ResourcesChanged": res_change,
                "ResourcesDeleted": res_delete,
            },
            outputs=outputs,
        )
