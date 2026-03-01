# Environment Strategy

This project uses three deployment stages:
- `dev`
- `staging`
- `prod`

## Source of truth
- `samconfig.toml`: SAM CLI configuration per stage.
- `infra/environments/<stage>.env`: stage-specific parameter values.

## Required runtime variables
Lambdas validate required variables at startup via `shared.config.validate_runtime_env()`:
- `STAGE`
- `SERVICE_NAME`
- `CONVERSATIONS_TABLE`
- `MESSAGES_TABLE`
- `APPOINTMENTS_TABLE`
- `PAYMENTS_TABLE`
- `OUTBOX_TABLE`
- `IDEMPOTENCY_TABLE`

Operational knobs (configured by SAM parameters):
- `AGGREGATION_WINDOW_SECONDS`
- `PAYMENT_TIMEOUT_MINUTES`
- `MAX_RESCHEDULES`
- `HANDOFF_TTL_MINUTES`
- `OUTBOX_MAX_RETRIES`
- `MAX_TOKENS_PER_TURN`

## Secrets conventions
Secrets are never hardcoded in repository files.
Store and reference them per stage using AWS Secrets Manager:
- `/secretaria-ia/dev/whatsapp`
- `/secretaria-ia/staging/whatsapp`
- `/secretaria-ia/prod/whatsapp`
- `/secretaria-ia/<stage>/payment-gateway`
- `/secretaria-ia/<stage>/llm-provider`

Suggested secret keys:
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `PAYMENT_WEBHOOK_SECRET`
- `LLM_API_KEY`
- `GEMINI_API_KEY`

## Rotation notes
- Rotate secrets directly in Secrets Manager and keep the same secret name/id.
- Lambda cold starts automatically read the newest value.
- Warm containers cache values in-memory for performance; forcing new deployments refreshes all containers quickly.

## Deployment usage
```powershell
./scripts/sam-validate.ps1 -Stage dev
./scripts/sam-build.ps1 -Stage dev
./scripts/sam-deploy-guided.ps1 -Stage dev
```

For first deployment in a new account/region:
```powershell
./scripts/sam-deploy-guided.ps1 -Stage dev -Guided
```

## Cost and reliability parameters in env files
Each `infra/environments/<stage>.env` now defines:
- queue retry and DLQ thresholds (`QUEUE_MAX_RECEIVE_COUNT`)
- monthly budget (`MONTHLY_BUDGET_USD`)
- orchestrator latency target (`ORCHESTRATOR_P95_LATENCY_MS`)
