# Changelog

## [0.1.7] 2024/12/11

* Fixed an issue that occured when running the command `preview`. When a module deployment B has a dependency on module deployment A, and if no changes to be made were found for the module deployment A, the preview of module deployment B used to fail with the following error message: `Unable to preview changes as this deployment is dependent on other deployments with pending changes`. Now, it does not fail anymore.

## [0.1.6] 2024/10/03

* Fixed issue with Terraform engines: Custom provider configuration in `override.tf` such as specific provider version are now taken in consideration during destroy operations. Before that, the latest provider version was used which might have led to inconsistencies.

## [0.1.5] 2024/02/08

* Added a command `remove-orphans` to remove orphaned orphaned module deployments from the package state corresponding to AWS accounts that no longer exist in the AWS organization or regions that are no longer enabled in an account.

## [0.1.4] 2024/01/19

* Fixed bug in package definition validation module preventing from using the `ConcurrentWorkers` attribute.
* Fixed bug with Terraform engines: with newer Terraform versions, providers must be downloaded if the lock file doesn't exist, even if providers exist in the shared cache. To prevent that from happening and keep bandwidth usage low, I set the environment variable `TF_PLUGIN_CACHE_MAY_BREAK_DEPENDENCY_LOCK_FILE` to `true`.

## [0.1.3] 2023/09/20

* Disallowed additional properties in the YAML package definition file. That might break upgrade to future versions if we add new properties, but this reduces the likehood to make mistakes today (e.g. attribute `Variables` not correctly indented).
* Removed the CLI argument `--disable-periodic-state-saving` and introduced the CLI argument `--save-state-every-seconds`. Previously, the package state was saved to S3 every 10 seconds during the execution of a `apply` or `update-hash` command. However, if the execution takes a lot of time, this could lead to a large number of object versions in S3. We changed the default behavior: the package state is now only saved at the end of the execution, unless the new CLI argument is specified.

## [0.1.2] 2023/09/15

* Add support of the CLI argument `--disable-periodic-state-saving` for the command `apply`. By default, AWS Orga Deployer saves the package state every 10 seconds during the execution of the command `apply`. This enables to recover from an eventual crash of AWS Orga Deployer without losing the information that certain deployments may have completed. However, this can lead to a large number of object versions in S3.
* Fixed a bug that prevented to gracefully exit the execution of Terraform modules, because the propagation of SIGINT signals did not work as expected.

## [0.1.1] 2023/09/13

* Added support for the `IgnoreIfNotExists` attribute in the package definition file to ignore dependencies that do not exist.
* Fixed a typo in the default name of the temporary folder created by AWS Orga Deployer (changed from `.aws_orga_deployer` to `.aws-orga-deployer`).
* Fixed a bug when referencing the output of another deployment using `VariablesFromOutputs`: if the output does not exist, the variable was set to `None` which could replace the default value defined by the `Variables` attribute. Now, the variable is not added or updated if the dependent output does not exist.

## [0.1.0] 2023/08/18

Initial release.
