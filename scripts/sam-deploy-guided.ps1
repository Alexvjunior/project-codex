param(
  [string]$TemplatePath = "infra/template.yaml",
  [string]$StackName = "secretaria-ia-dev",
  [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"
sam deploy --guided --template-file $TemplatePath --stack-name $StackName --region $Region
