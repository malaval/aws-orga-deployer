# Changelog

## [0.1.1] 2023/09/13

* Added support for the `IgnoreIfNotExists` attribute in the package definition file to ignore dependencies that do not exist.
* Fixed a typo in the default name of the temporary folder created by AWS Orga Deployer (changed from `.aws_orga_deployer` to `.aws-orga-deployer`).
* Fixed a bug when referencing the output of another deployment using `VariablesFromOutputs`: if the output does not exist, the variable was set to `None` which could replace the default value defined by the `Variables` attribute. Now, the variable is not added or updated if the dependent output does not exist.

## [0.1.0] 2023/08/18

Initial release.
