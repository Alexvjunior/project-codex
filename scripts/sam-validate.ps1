param(
  [string]$TemplatePath = "infra/template.yaml"
)

$ErrorActionPreference = "Stop"
sam validate --template-file $TemplatePath
