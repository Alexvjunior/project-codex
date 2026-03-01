param(
  [string]$TemplatePath = "infra/template.yaml",
  [string]$Stage = "dev"
)

$ErrorActionPreference = "Stop"
sam validate --template-file $TemplatePath --config-file samconfig.toml --config-env $Stage --lint
