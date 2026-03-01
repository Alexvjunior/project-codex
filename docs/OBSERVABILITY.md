# Observability and Correlation

## Structured logs
All lambda handlers emit JSON logs with:
- `timestamp`
- `level`
- `message`
- `correlation_id`
- `service`
- `stage`
- `function_name`

Implementation: `layers/shared/python/shared/logging_utils.py`.

## Correlation ID flow
- HTTP requests: from `x-correlation-id` header when present, otherwise generated.
- SQS events: propagated in event payload (`correlation_id`).
- HTTP responses: include `x-correlation-id` header.

This enables tracing a request across:
- `ingest-whatsapp`
- `message-aggregator`
- `conversation-orchestrator`
- `whatsapp-sender`

## Healthcheck endpoints
- `GET /health/ingest`
- `GET /health/payment`

## CloudWatch alarms and dashboard
Implemented in `infra/template.yaml`:
- Lambda error alarms:
  - `*-payment-webhook-errors`
  - `*-conversation-orchestrator-errors`
- Latency alarm:
  - `*-conversation-orchestrator-p95-latency`
- Queue age alarms:
  - `*-inbound-queue-age`
  - `*-outbound-queue-age`
- DLQ depth alarms:
  - `*-inbound-dlq-depth`
  - `*-turn-dlq-depth`
  - `*-outbound-dlq-depth`

Dashboard:
- `secretaria-ia-<stage>-ops`
  - Lambda errors
  - SQS oldest message age
  - Orchestrator duration p95
  - DLQ visible messages
