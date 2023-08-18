resource "aws_ssm_parameter" "test" {
  name  = "test"
  type  = "String"
  value = var.varTerraform1
}

output "SSMParameterARN" {
  value = aws_ssm_parameter.test.arn
}