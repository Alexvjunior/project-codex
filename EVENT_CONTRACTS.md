# Contratos de Eventos (MVP)

## Envelope Padrão
Todo evento publicado internamente deve seguir este formato:

```json
{
  "event_id": "uuid",
  "event_type": "string",
  "event_version": 1,
  "occurred_at": "2026-03-01T12:00:00Z",
  "correlation_id": "uuid",
  "causation_id": "uuid-or-null",
  "tenant_id": "nutri_123",
  "session_id": "nutri_123:+5511999999999",
  "idempotency_key": "string",
  "payload": {}
}
```

## Regras de Versionamento
- Nome do evento com sufixo `.vN` (ex.: `whatsapp.message.received.v1`).
- Inclusão de novos campos na mesma versão apenas como opcionais.
- Mudança incompatível cria nova versão (`v2`, `v3`, ...).

## Eventos do MVP

### 1) `whatsapp.message.received.v1`
- **Producer:** `ingest-whatsapp`
- **Consumer:** `message-aggregator`
- **Idempotency:** `channel_message_id`

```json
{
  "channel_message_id": "wamid.HBgL...",
  "from": "+5511999999999",
  "to": "+5511888888888",
  "is_echo": false,
  "text": "Oi, quero agendar",
  "received_at": "2026-03-01T12:00:00Z",
  "raw_type": "text"
}
```

### 2) `conversation.turn.ready.v1`
- **Producer:** `message-aggregator`
- **Consumer:** `conversation-orchestrator`
- **Idempotency:** `session_id:turn_started_at`

```json
{
  "turn_id": "uuid",
  "messages": [
    {"message_id":"wamid1","from":"PATIENT","text":"Oi"},
    {"message_id":"wamid2","from":"PATIENT","text":"quero consulta"}
  ],
  "window_seconds": 15,
  "state_version": 7
}
```

### 3) `whatsapp.message.send.requested.v1`
- **Producer:** `conversation-orchestrator`, `payment-webhook`
- **Consumer:** `whatsapp-sender`
- **Idempotency:** `session_id:out_msg_hash`

```json
{
  "outbox_id": "out_123",
  "to": "+5511999999999",
  "messages": [
    {"type":"text","text":"Perfeito! Tenho quarta às 14h."}
  ],
  "context": {"appointment_id":"apt_123"},
  "attempt": 0
}
```

### 4) `appointment.upserted.v1`
- **Producer:** `conversation-orchestrator`
- **Consumer:** `storage projection` (ou persistência inline no orchestrator)
- **Idempotency:** `appointment_id:status:updated_at`

```json
{
  "appointment_id": "apt_123",
  "patient_id": "pat_456",
  "status": "PAYMENT_PENDING",
  "slot_start": "2026-03-10T17:00:00Z",
  "slot_end": "2026-03-10T18:00:00Z",
  "calendar_event_id": "gcal_abc"
}
```

### 5) `payment.webhook.received.v1`
- **Producer:** `payment-webhook` (payload externo normalizado)
- **Consumer:** handler determinístico de pagamento
- **Idempotency:** `gateway_event_id`

### 6) `payment.confirmed.v1`
- **Producer:** `payment-webhook`
- **Consumer:** `whatsapp-sender` e projeções de domínio
- **Idempotency:** `gateway_payment_id:approved`

```json
{
  "appointment_id": "apt_123",
  "payment_id": "pay_789",
  "gateway_payment_id": "mp_456",
  "amount": 250.0,
  "currency": "BRL",
  "paid_at": "2026-03-01T12:30:00Z"
}
```

## Garantias Operacionais
- Semântica de entrega: at-least-once.
- Consumidores obrigatoriamente idempotentes.
- Ordem por sessão garantida via `SQS FIFO MessageGroupId = session_id`.
