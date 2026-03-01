# Go-Live Checklist (MVP)

## SLO inicial publicado
- Disponibilidade de processamento ponta a ponta (ingestao ate envio): `>= 99.0%` por semana.
- Latencia p95 do `conversation-orchestrator`: `<= 5s`.
- Tempo para fila vazia apos incidente: `<= 30 min`.

## Checklist tecnico
1. Infra SAM validada e deploy sem drift nos ambientes alvo.
2. Secrets de WhatsApp, pagamento e LLM configurados por stage.
3. Alarmes ativos e assinante de email confirmado.
4. Dashboard `secretaria-ia-<stage>-ops` disponivel.
5. Filas com DLQ configuradas e script de reprocessamento testado.
6. `payment-webhook` validando assinatura com segredo real.
7. Fluxos de negocio validados em ambiente de homologacao:
   - agendamento
   - pagamento confirmado
   - remarcacao dentro do limite
   - cancelamento com politica de pagamento
   - handoff humano `/ia off` e `/ia on`.

## Checklist de operacao
1. Runbooks revisados com time responsavel.
2. Responsavel de on-call definido para horario comercial.
3. Procedimento de rollback documentado (redeploy versao anterior).
4. Canal de incidente definido (Slack/WhatsApp interno/email).

## Itens adiados (fase final)
- Testes de integracao E2E automatizados completos (issues de teste).
- Suite com conversas reais anonimizadas.

## Criterio para iniciar producao
Liberar producao somente quando todos os itens tecnicos e operacionais acima estiverem `OK`.
