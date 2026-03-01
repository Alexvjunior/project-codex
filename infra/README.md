# Infraestrutura Base (ISS-001)

Este diretório contém a stack inicial AWS SAM para o MVP da Secretária IA.

## Recursos Provisionados
- 1 Lambda Layer compartilhada (`shared`) para evitar duplicação de código entre funções
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
./scripts/sam-validate.ps1 -Stage dev
./scripts/sam-build.ps1 -Stage dev
./scripts/sam-deploy-guided.ps1 -Stage dev
```

## Parâmetros importantes
- `ServiceName`: prefixo dos recursos.
- `Stage`: ambiente (`dev`, `staging`, `prod`).
- `LogRetentionDays`: retenção dos logs.
- `AlarmEmail`: e-mail para receber alarmes CloudWatch (opcional).
- `WhatsAppSecretId`: secret id no Secrets Manager para credenciais Meta.
- `PaymentSecretId`: secret id para credenciais do gateway de pagamento.
- `LlmSecretId`: secret id para credenciais do provedor LLM.

## Estratégia de ambientes
- Configuração SAM por ambiente: `samconfig.toml`
- Valores por stage: `infra/environments/dev.env`, `staging.env`, `prod.env`
- Convenções de segredos: `docs/ENVIRONMENTS.md`

## Packaging de Lambda
- Cada função usa `CodeUri` específico, enviando somente o código necessário da função.
- Código compartilhado é publicado separadamente na layer `shared`.
- Resultado: artefatos menores por Lambda e deploy mais eficiente.
