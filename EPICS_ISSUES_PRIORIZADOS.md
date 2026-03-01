# Épicos e Issues Priorizados (MVP)

## Convenções
- Prioridade: `P0` (bloqueante MVP), `P1` (essencial MVP), `P2` (hardening/go-live).
- Estimativa: dias úteis de implementação.
- Dependências: IDs de issues que precisam estar concluídas antes.

## Épicos

| Epic ID | Nome | Prioridade | Objetivo | Dependências |
|---|---|---|---|---|
| EPIC-01 | Fundação de Plataforma | P0 | Subir base AWS, ambientes, secrets e observabilidade mínima | - |
| EPIC-02 | Ingestão e Entrega Confiáveis | P0 | Garantir entrada/saída idempotente no WhatsApp | EPIC-01 |
| EPIC-03 | Orquestração de Conversa com LangGraph | P1 | Processar turnos, decidir tools e responder com contexto | EPIC-02 |
| EPIC-04 | Agenda e Pagamento Determinísticos | P1 | Fechar fluxo de reserva e confirmação por webhook | EPIC-03 |
| EPIC-05 | Remarcação, Cancelamento e Handoff Humano | P1 | Completar operações de pós-agendamento com controle humano | EPIC-04 |
| EPIC-06 | Hardening de Produção | P2 | Garantir operação contínua com testes, alertas e runbooks | EPIC-05 |

## Issues Priorizadas (ordem de execução)

| Issue ID | Título | Epic | Prioridade | Estimativa | Dependências |
|---|---|---|---|---|---|
| ISS-001 | Provisionar infraestrutura base (API Gateway, Lambda, SQS FIFO, DynamoDB, CloudWatch) | EPIC-01 | P0 | 2d | - |
| ISS-002 | Configurar ambientes `dev/staging/prod` e variáveis por ambiente | EPIC-01 | P0 | 1d | ISS-001 |
| ISS-003 | Integrar Secrets Manager para credenciais (Meta, gateway, LLM) | EPIC-01 | P0 | 1d | ISS-001 |
| ISS-004 | Implementar padrão de logs estruturados com `correlation_id` | EPIC-01 | P0 | 1d | ISS-001 |
| ISS-005 | Criar pipeline de deploy automatizado para `dev` | EPIC-01 | P0 | 1d | ISS-002, ISS-003 |
| ISS-006 | Expor healthcheck técnico de funções críticas | EPIC-01 | P0 | 0.5d | ISS-001 |
| ISS-007 | Implementar Lambda `ingest-whatsapp` com validação de assinatura | EPIC-02 | P0 | 1d | ISS-003 |
| ISS-008 | Normalizar payload WhatsApp para contrato interno `whatsapp.message.received.v1` | EPIC-02 | P0 | 1d | ISS-007 |
| ISS-009 | Implementar deduplicação por `channel_message_id` com escrita condicional | EPIC-02 | P0 | 1d | ISS-008 |
| ISS-010 | Publicar eventos de entrada em `SQS FIFO inbound` com ordenação por sessão | EPIC-02 | P0 | 0.5d | ISS-008 |
| ISS-011 | Implementar tabela `Outbox` e contrato `whatsapp.message.send.requested.v1` | EPIC-02 | P0 | 1d | ISS-001 |
| ISS-012 | Implementar Lambda `whatsapp-sender` com retry exponencial e idempotência | EPIC-02 | P0 | 1d | ISS-011 |
| ISS-013 | Persistir mensagens brutas e normalizadas com TTL em `Messages` | EPIC-02 | P1 | 1d | ISS-009 |
| ISS-014 | Implementar `message-aggregator` com janela de 10-20s | EPIC-03 | P1 | 1d | ISS-010 |
| ISS-015 | Publicar `conversation.turn.ready.v1` para fila de turnos | EPIC-03 | P1 | 0.5d | ISS-014 |
| ISS-016 | Implementar `conversation-orchestrator` base com LangGraph | EPIC-03 | P1 | 2d | ISS-015 |
| ISS-017 | Implementar máquina de estados de conversa (`ACTIVE`, `WAIT_PAYMENT`, `HANDOFF_HUMAN`) | EPIC-03 | P1 | 1.5d | ISS-016 |
| ISS-018 | Implementar RAG v1 (examples/playbook/faq) com top-k e fallback | EPIC-03 | P1 | 1.5d | ISS-016 |
| ISS-019 | Implementar tool `rag_retriever` integrada ao orchestrator | EPIC-03 | P1 | 0.5d | ISS-018 |
| ISS-020 | Implementar trilha de decisão do agent (logs de tool calls e transições) | EPIC-03 | P1 | 1d | ISS-017 |
| ISS-021 | Implementar integração `calendar_search` | EPIC-04 | P1 | 1d | ISS-017 |
| ISS-022 | Implementar integração `calendar_book` com idempotência | EPIC-04 | P1 | 1d | ISS-021 |
| ISS-023 | Implementar `payment_generate` e persistência inicial de cobrança | EPIC-04 | P1 | 1d | ISS-022 |
| ISS-024 | Implementar Lambda `payment-webhook` com validação de assinatura | EPIC-04 | P1 | 1d | ISS-003 |
| ISS-025 | Implementar dedupe de `gateway_event_id` e processamento atômico de webhook | EPIC-04 | P1 | 1d | ISS-024 |
| ISS-026 | Implementar atualização transacional em `Appointments` e `Payments` | EPIC-04 | P1 | 1d | ISS-025 |
| ISS-027 | Emitir confirmação ao paciente após `payment.confirmed.v1` | EPIC-04 | P1 | 0.5d | ISS-026, ISS-012 |
| ISS-028 | Teste de integração E2E do fluxo completo (interesse -> confirmação) | EPIC-04 | P1 | 1.5d | ISS-027 |
| ISS-029 | Implementar fluxo de remarcação com regras de negócio e limites | EPIC-05 | P1 | 1.5d | ISS-028 |
| ISS-030 | Implementar fluxo de cancelamento com política de status/reembolso | EPIC-05 | P1 | 1d | ISS-028 |
| ISS-031 | Implementar estado `HANDOFF_HUMAN` com comando `/ia on` | EPIC-05 | P1 | 1d | ISS-017 |
| ISS-032 | Implementar timeout de pagamento e liberação automática de slot | EPIC-05 | P1 | 1d | ISS-026 |
| ISS-033 | Cobrir remarcação/cancelamento/handoff com testes de integração | EPIC-05 | P1 | 1.5d | ISS-029, ISS-030, ISS-031, ISS-032 |
| ISS-034 | Criar suíte E2E com conversas reais anonimizadas | EPIC-06 | P2 | 2d | ISS-033 |
| ISS-035 | Montar dashboards e alarmes CloudWatch (erros, latência, fila) | EPIC-06 | P2 | 1d | ISS-020 |
| ISS-036 | Criar runbooks de incidente e reprocessamento de filas | EPIC-06 | P2 | 1d | ISS-035 |
| ISS-037 | Implementar controles de custo (token budget, alarmes de consumo) | EPIC-06 | P2 | 1d | ISS-018, ISS-035 |
| ISS-038 | Fechar checklist de go-live com SLO inicial publicado | EPIC-06 | P2 | 1d | ISS-034, ISS-036, ISS-037 |

## Marco de Entrega (Milestones)

| Milestone | Critério para concluir |
|---|---|
| M1 - Plataforma Operável | ISS-001 até ISS-013 concluídas |
| M2 - Conversa Inteligente | ISS-014 até ISS-020 concluídas |
| M3 - Agendamento Pago | ISS-021 até ISS-028 concluídas |
| M4 - Operação Completa | ISS-029 até ISS-033 concluídas |
| M5 - Pronto para Produção | ISS-034 até ISS-038 concluídas |

## Definição de Pronto (DoR) por Issue
- Contrato de evento afetado identificado.
- Tabela DynamoDB e chaves definidas (se aplicável).
- Critério de teste (unitário/integrado/E2E) descrito.
- Impacto de custo estimado (tokens/chamadas/API).

## Definição de Feito (DoD) por Issue
- Código em `main` com revisão.
- Testes da issue passando.
- Logs/métricas relevantes publicados.
- Documentação atualizada (arquitetura/estado/contrato quando houver mudança).
