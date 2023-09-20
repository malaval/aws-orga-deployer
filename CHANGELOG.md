# Changelog

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
