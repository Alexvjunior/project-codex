param(
  [string]$TemplatePath = "infra/template.yaml",
  [string]$BuildDir = ".aws-sam/build"
)

$ErrorActionPreference = "Stop"
sam build --template-file $TemplatePath --build-dir $BuildDir
