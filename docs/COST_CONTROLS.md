# Cost Controls

## Objetivo
Manter o MVP com custo previsivel em AWS e uso de LLM controlado.

## Controles implementados
1. Token budget por turno:
   - variavel `MAX_TOKENS_PER_TURN`
   - mensagens acima do limite nao entram no fluxo normal e pedem resumo ao usuario.
2. Budget mensal da conta:
   - recurso `AWS::Budgets::Budget` (`MonthlyCostBudget`)
   - alerta por email em 80% do limite (`MonthlyBudgetUsd`).
3. Alarmes operacionais:
   - erros em Lambdas criticas
   - fila envelhecida (proxy de custo por retry/backlog)
   - DLQ com mensagens acumuladas.
4. Packaging enxuto:
   - `CodeUri` por funcao
   - codigo compartilhado em `Lambda Layer`.

## Parametros de custo
Definidos por ambiente em `infra/environments/*.env`:
- `MAX_TOKENS_PER_TURN`
- `MONTHLY_BUDGET_USD`
- `OUTBOX_MAX_RETRIES`
- `QUEUE_MAX_RECEIVE_COUNT`

## Recomendacoes de operacao
1. Comecar com `MonthlyBudgetUsd` conservador (dev: 20, staging: 30, prod: 50).
2. Revisar mensalmente custo de:
   - DynamoDB On-demand
   - Lambda Duration
   - chamadas externas (LLM e WhatsApp).
3. Ajustar `MAX_TOKENS_PER_TURN` antes de aumentar orçamento.
4. Reduzir retries agressivos antes de escalar capacidade.
