param(
  [string]$TemplatePath = "infra/template.yaml",
  [ValidateSet("dev", "staging", "prod")]
  [string]$Stage = "dev",
  [string]$Region = "us-east-1",
  [switch]$Guided
)

$ErrorActionPreference = "Stop"

function Read-EnvFile([string]$Path) {
  $map = @{}
  Get-Content -Path $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) {
      $map[$parts[0].Trim()] = $parts[1].Trim()
    }
  }
  return $map
}

$envFile = Join-Path "infra/environments" "$Stage.env"
if (-not (Test-Path $envFile)) {
  throw "Environment file not found: $envFile"
}

$cfg = Read-EnvFile $envFile
$serviceName = $cfg["SERVICE_NAME"]
$stackStage = $cfg["STAGE"]
$logRetention = $cfg["LOG_RETENTION_DAYS"]
$messageTtl = $cfg["MESSAGE_TTL_DAYS"]
$paymentTtl = $cfg["PAYMENT_TTL_DAYS"]
$alarmEmail = $cfg["ALARM_EMAIL"]
$whatsAppSecretId = $cfg["WHATSAPP_SECRET_ID"]
$paymentSecretId = $cfg["PAYMENT_SECRET_ID"]
$llmSecretId = $cfg["LLM_SECRET_ID"]

$stackName = "$serviceName-$stackStage"
$overrides = @(
  "ServiceName=$serviceName",
  "Stage=$stackStage",
  "LogRetentionDays=$logRetention",
  "MessageTtlDays=$messageTtl",
  "PaymentTtlDays=$paymentTtl",
  "AlarmEmail=$alarmEmail",
  "WhatsAppSecretId=$whatsAppSecretId",
  "PaymentSecretId=$paymentSecretId",
  "LlmSecretId=$llmSecretId"
)

if ($Guided) {
  sam deploy --guided --template-file $TemplatePath --stack-name $stackName --region $Region --capabilities CAPABILITY_IAM --parameter-overrides $overrides
} else {
  sam deploy --template-file $TemplatePath --stack-name $stackName --region $Region --config-file samconfig.toml --config-env $Stage --resolve-s3 --capabilities CAPABILITY_IAM --parameter-overrides $overrides
}
