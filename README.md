# Secretaria IA - Project Codex

Base de implementacao do MVP de secretaria virtual para nutricionistas (WhatsApp + agenda + pagamento) em AWS.

## Status
- Foundation + fluxos core implementados:
  - ingestao, agregacao, orquestracao, webhook de pagamento, sender
  - estado de conversa, remarcacao/cancelamento/handoff, timeout de pagamento
  - observabilidade, DLQ, budget mensal e checklist de go-live
- Testes de integracao E2E foram adiados para a fase final.

## Estrutura
- `infra/`: template AWS SAM e documentacao de infraestrutura
- `layers/`: Lambda Layers compartilhadas
- `src/functions/`: Lambdas por responsabilidade
- `scripts/`: comandos operacionais de validate/build/deploy
- `*.md`: PRD, arquitetura, contratos e backlog

## Infra (rapido)
```powershell
./scripts/sam-validate.ps1 -Stage dev
./scripts/sam-build.ps1 -Stage dev
./scripts/sam-deploy-guided.ps1 -Stage dev
```

## Ambientes
- `samconfig.toml`: configuracao de deploy por ambiente (`dev`, `staging`, `prod`)
- `infra/environments/*.env`: parametros por stage
- `docs/ENVIRONMENTS.md`: estrategia de variaveis e segredos
- `.github/workflows/deploy-dev.yml`: deploy manual no ambiente `dev`
- `.github/workflows/deploy-prod.yml`: deploy manual para `prod` com confirmacao (`confirm_prod=DEPLOY`)

## Observabilidade e Saude
- Logs estruturados com `correlation_id`
- Endpoints de healthcheck: `GET /health/ingest`, `GET /health/payment`
- Detalhes em `docs/OBSERVABILITY.md`

## Operacao
- `docs/RUNBOOKS.md`: incidentes e reprocessamento
- `docs/COST_CONTROLS.md`: controles de custo e limites
- `docs/GO_LIVE_CHECKLIST.md`: checklist de entrada em producao e SLO inicial

## LLM (Gemini)
- O projeto le credenciais de LLM via AWS Secrets Manager (`LLM_SECRET_ID`).
- Chaves aceitas no secret: `GEMINI_API_KEY` ou `LLM_API_KEY`.
- No deploy de `prod` pelo GitHub Actions, a chave pode ser injetada por `secrets.GEMINI_API_KEY` em `GEMINI_API_KEY` da Lambda.
- Evite salvar API key em repositório ou variavel fixa em workflow.

## Packaging
- Cada Lambda e empacotada individualmente (CodeUri por funcao).
- Codigo compartilhado e entregue via Lambda Layer.
