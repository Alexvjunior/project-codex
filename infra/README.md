# Infraestrutura Base (ISS-001)

Este diretório contém a stack inicial AWS SAM para o MVP da Secretária IA.

## Recursos Provisionados
- API Gateway HTTP (`/whatsapp-webhook`, `/payment-webhook`)
- 5 Lambdas:
  - `ingest-whatsapp`
  - `message-aggregator`
  - `conversation-orchestrator`
  - `payment-webhook`
  - `whatsapp-sender`
- 3 filas SQS FIFO:
  - `inbound`
  - `turn`
  - `outbound`
- 6 tabelas DynamoDB:
  - `conversations`
  - `messages`
  - `appointments`
  - `payments`
  - `outbox`
  - `idempotency`
- CloudWatch:
  - Log Group com retenção configurável para cada Lambda
  - Alarmes de erro para `payment-webhook` e `conversation-orchestrator`
  - SNS opcional para notificação de alarmes

## Pré-requisitos
- AWS CLI configurado
- AWS SAM CLI instalado
- Python 3.11

## Comandos
```powershell
./scripts/sam-validate.ps1
./scripts/sam-build.ps1
./scripts/sam-deploy-guided.ps1 -StackName secretaria-ia-dev -Region us-east-1
```

## Parâmetros importantes
- `ServiceName`: prefixo dos recursos.
- `Stage`: ambiente (`dev`, `staging`, `prod`).
- `LogRetentionDays`: retenção dos logs.
- `AlarmEmail`: e-mail para receber alarmes CloudWatch (opcional).
