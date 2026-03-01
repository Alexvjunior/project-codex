param(
  [string]$TemplatePath = "infra/template.yaml",
  [string]$BuildDir = ".aws-sam/build",
  [string]$Stage = "dev"
)

$ErrorActionPreference = "Stop"
sam build --template-file $TemplatePath --build-dir $BuildDir --config-file samconfig.toml --config-env $Stage
