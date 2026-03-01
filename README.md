# Secretaria IA - Project Codex

Base de implementacao do MVP de secretaria virtual para nutricionistas (WhatsApp + agenda + pagamento) em AWS.

## Status
- `ISS-001` em andamento: infraestrutura fundacional com AWS SAM.

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

## Packaging
- Cada Lambda e empacotada individualmente (CodeUri por funcao).
- Codigo compartilhado e entregue via Lambda Layer.
