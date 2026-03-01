# Runbooks de Operacao

## Escopo
Runbooks para incidentes do MVP:
- atraso em filas SQS
- mensagens em DLQ
- erros de webhook de pagamento
- falha no envio WhatsApp

## 1) Fila com backlog alto
Sinal:
- alarmes `*-inbound-queue-age` ou `*-outbound-queue-age` acionados.

Passos:
1. Abrir dashboard `secretaria-ia-<stage>-ops`.
2. Validar se `Lambda Errors` aumentou no mesmo periodo.
3. Identificar funcao com erro em CloudWatch Logs por `correlation_id`.
4. Corrigir causa raiz.
5. Confirmar queda de `ApproximateAgeOfOldestMessage` para < 30s.

## 2) DLQ com mensagens visiveis
Sinal:
- alarmes `*-dlq-depth` acionados.

Passos:
1. Pausar deploys ate entender causa raiz.
2. Ler 5 mensagens da DLQ e classificar causa (payload invalido, dependencia fora, bug).
3. Corrigir causa raiz.
4. Reprocessar mensagens com script:

```powershell
./scripts/reprocess-dlq.ps1 `
  -SourceQueueArn arn:aws:sqs:us-east-1:<account>:secretaria-ia-dev-turn-dlq.fifo `
  -DestinationQueueArn arn:aws:sqs:us-east-1:<account>:secretaria-ia-dev-turn.fifo `
  -MessagesPerSecond 20
```

5. Confirmar `DLQ Visible Messages` = 0 no dashboard.

## 3) Webhook de pagamento com erro
Sinal:
- alarme `*-payment-webhook-errors`.
- respostas HTTP 401/5xx no endpoint `/payment-webhook`.

Passos:
1. Validar assinatura enviada (`x-payment-signature`) e segredo `PAYMENT_WEBHOOK_SECRET`.
2. Verificar se o `gateway_event_id` ja foi processado (dedupe esperado).
3. Confirmar transacao DynamoDB em `Payments` e `Appointments`.
4. Se necessario, solicitar reenvio do webhook no gateway.

## 4) Falha no envio WhatsApp
Sinal:
- `whatsapp-sender` com muitos retries/failed.
- aumento de registros `Outbox.status=FAILED`.

Passos:
1. Validar segredo WhatsApp (`WHATSAPP_ACCESS_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID`).
2. Checar resposta HTTP da Meta nos logs.
3. Apos correcao, reenfileirar mensagens com falha via `OutboundDlq` (se estiver em DLQ).
4. Revalidar taxa de envio e zerar falhas pendentes.

## Comunicacao de incidente
Checklist minimo:
1. Horario de inicio do incidente.
2. Impacto (quantas conversas afetadas).
3. Causa raiz.
4. Mitigacao aplicada.
5. Acao preventiva.
