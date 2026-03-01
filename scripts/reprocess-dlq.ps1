param(
  [Parameter(Mandatory = $true)]
  [string]$SourceQueueArn,
  [Parameter(Mandatory = $true)]
  [string]$DestinationQueueArn,
  [int]$MessagesPerSecond = 20
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
  throw "AWS CLI nao encontrado no PATH."
}

$result = aws sqs start-message-move-task `
  --source-arn $SourceQueueArn `
  --destination-arn $DestinationQueueArn `
  --max-number-of-messages-per-second $MessagesPerSecond `
  --output json

Write-Output $result
