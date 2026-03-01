# Backlog Técnico de Implementação (MVP em Fases)

## Objetivo
Entregar um MVP funcional, barato e seguro para operação via WhatsApp com agendamento e pagamento.

## Fase 0 - Fundacional (3-5 dias)
### Escopo
- Provisionar infraestrutura base (API Gateway, Lambda, SQS FIFO, DynamoDB, CloudWatch).
- Configuração de ambientes (`dev`, `staging`, `prod`) e secrets.
- Padrão de logs estruturados + correlação (`correlation_id`).

### DoD
- Deploy automatizado em `dev`.
- Healthcheck de APIs/Lambdas.
- Métricas básicas de erro e latência ativas.

## Fase 1 - Entrada/Saída Confiável (4-6 dias)
### Escopo
- Implementar `ingest-whatsapp` com validação de assinatura.
- Implementar deduplicação por `channel_message_id`.
- Implementar `whatsapp-sender` com outbox + retry.
- Persistir mensagens brutas e normalizadas.

### DoD
- Entrada e saída com idempotência ponta a ponta.
- Reentrega não gera mensagem duplicada para o paciente.

## Fase 2 - Orquestração de Conversa (5-7 dias)
### Escopo
- Implementar `message-aggregator` com janela 10-20s.
- Implementar `conversation-orchestrator` com LangGraph.
- Implementar RAG v1 (`examples`, `playbook`, `faq`) com top-k.
- Resposta contextual com tom configurável por nutricionista.

### DoD
- Fluxo de conversa do primeiro contato até oferta de horários funcionando.
- Logs com trilha de decisão do agent e tools chamadas.

## Fase 3 - Agenda + Pagamento (5-7 dias)
### Escopo
- Tools: `calendar_search`, `calendar_book`, `payment_generate`.
- Implementar `payment-webhook` determinístico (assinatura + dedupe).
- Atualização transacional de `Appointments` e `Payments`.
- Mensagem de confirmação automática após pagamento aprovado.

### DoD
- `CONFIRMED` somente por webhook válido.
- Fluxo completo: interesse -> reserva -> pagamento -> confirmação.

## Fase 4 - Remarcação/Cancelamento + Handoff Humano (4-6 dias)
### Escopo
- Implementar fluxos de remarcação/cancelamento.
- Implementar estado `HANDOFF_HUMAN`.
- Reativação por comando (`/ia on`) e timeout de hibernação.
- Políticas de expiração de pagamento e liberação de slot.

### DoD
- Remarcação e cancelamento cobertos por testes de integração.
- Bot não responde durante handoff humano.

## Fase 5 - Hardening Produção (4-6 dias)
### Escopo
- Testes e2e com conversas reais anonimizadas.
- Dashboards e alarmes operacionais.
- Runbooks de incidente e reprocessamento de filas.
- Controles de custo e limites por tenant.

### DoD
- Checklist de go-live aprovado.
- SLO inicial publicado (latência, erro, disponibilidade).

## Critérios de Aceite do MVP
1. `p95` de resposta ao paciente menor que 8 segundos (sem contar espera de pagamento).
2. Zero confirmação de consulta sem webhook de pagamento válido.
3. Idempotência comprovada em entrada, saída e webhook.
4. Handoff para humano auditável e reversível.

## Dependências Externas
- WhatsApp Cloud API (Meta).
- Google Calendar API.
- Gateway de pagamento (Mercado Pago/PagSeguro).
- Provedor LLM (Gemini/OpenAI/Anthropic) por custo/token.

## Riscos e Mitigações
- Instabilidade em APIs externas: retry com backoff e mensagens de fallback humanizadas.
- Duplicidade de eventos: idempotency keys + escrita condicional no DynamoDB.
- Custo de tokens: janela curta de contexto + RAG enxuto + cache de prompts.
