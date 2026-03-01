PRD: Secretária IA Autônoma com RAG de Exemplos1. Descrição do ProjetoO sistema é uma Secretária Virtual inteligente para nutricionistas, operando via WhatsApp. Diferente de bots lineares, este agente utiliza LangGraph para raciocínio autônomo e RAG para consultar um banco de exemplos de conversas (JSON), permitindo que ele aprenda o tom de voz e as melhores decisões com base em interações passadas.+42. Arquitetura Técnica (AWS us-east-1)

Componentes Principais:

**Interface:** WhatsApp Cloud API (Meta).

**API Gateway (Genérico):** HTTP API como ponto de entrada único e roteador.
  - `/whatsapp-webhook` → Lambda message-buffer → Lambda whats-agent
  - `/payment-webhook` → Lambda payment-webhook (sem agent, processamento direto)
  - Preparado para futuras rotas: `/telegram-webhook`, `/sms-webhook`, etc.
  - Escalável para múltiplos agents e canais

**Processamento:** AWS Lambda (Python 3.11+).
  - `message-buffer`: Agrega mensagens por 2 minutos antes de processar
  - `whats-agent`: LangGraph com agents (Patient Agent, Nutri Agent). O acesso ao Google Calendar e a geração de link de pagamento acontecem **dentro do agente via tools** — o LLM decide autonomamente quando e como usá-las
  - `payment-webhook`: Recebe e processa webhooks do gateway de pagamento (sem LLM/agent — lógica determinística pura)

**Orquestração:** LangGraph (Estado e Ferramentas) dentro do whats-agent.

**RAG Engine:** Sistema de busca semântica em examples.json para few-shot prompting.

**Banco de Dados:** DynamoDB com 3 tabelas:
  - `SessionMessages`: Mensagens e estado de conversa (PK: sessionId, SK: timestamp ou "STATE")
  - `Appointments`: Consultas agendadas (PK: nutriId, SK: datetime#appointmentId)
  - `Payments`: Pagamentos (PK: appointmentId, SK: paymentId)3. O Componente RAG (Cérebro do Sistema)

O agente NÃO usa regras programáticas (if/else). Todo comportamento emerge dos exemplos RAG.

Funcionamento: Antes de cada resposta, o agente busca as 3 conversas mais similares ao contexto atual no JSON.

Uso: Esses exemplos são inseridos no System Prompt (Few-shot learning). O LLM aprende:
  - Tom de voz e uso de emojis
  - Quando perguntar vs quando agir diretamente
  - Como lidar com objeções de preço
  - Quando encaminhar para a nutricionista
  - Sequência natural de agendamento

Filosofia: "Mostre exemplos, não dê regras". O agente imita o comportamento demonstrado nos exemplos, não segue lógica programada.4. Estrutura de Dados (DynamoDB)

**Tabela 1: SessionMessages**
Armazena mensagens e estado de cada sessão de conversa.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| PK | String | `sessionId` (nutriId + número do paciente) |
| SK | String | `timestamp` (ISO) ou `"STATE"` para registro de estado |
| from | String | `PACIENTE` \| `NUTRI` \| `SYSTEM` |
| direction | String | `IN` \| `OUT` |
| messageId | String | ID da mensagem do WhatsApp |
| body | String | Conteúdo da mensagem |
| metaJson | String | JSON com dados extras (tipo, canal, anexos) |
| ttl | Number | Timestamp para expiração (7 dias) |

**Item Especial: Conversation State (SK = "STATE")**
| Campo | Descrição |
|-------|-----------|
| role | `PACIENTE` \| `NUTRI` |
| flow | `NORMAL` \| `RESCHEDULE` \| `ASK_NUTRI` \| `SEND_FILE` |
| appointmentId | ID da consulta em contexto |
| step | Etapa atual do fluxo |
| lastMessageAt | Timestamp da última mensagem |
| lastAgentRunAt | Timestamp da última execução do agent |
| hibernationUntil | Timestamp de hibernação (quando nutri assumiu) |
| extraState | JSON com dados específicos do fluxo |

**Tabela 2: Appointments**
Consultas agendadas e histórico.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| PK | String | `nutriId` (partition key) |
| SK | String | `datetime#appointmentId` (sort key) |
| appointmentId | String | UUID da consulta |
| patientId | String | ID único do paciente |
| patientWhatsapp | String | Número WhatsApp |
| patientName | String | Nome do paciente |
| status | String | `scheduled` \| `canceled` \| `reschedule_pending` |
| paymentStatus | String | `pending` \| `paid` \| `refunded` |
| calendarEventId | String | ID do evento no Google Calendar |
| durationMinutes | Number | Duração (padrão: 60) |
| metaJson | String | Dados extras |

**Tabela 3: Payments**
Registros de pagamento.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| PK | String | `appointmentId` (partition key) |
| SK | String | `paymentId` (sort key) |
| gatewayPaymentId | String | ID no gateway (Mercado Pago, etc.) |
| status | String | `pending` \| `paid` \| `failed` |
| amount | Number | Valor em reais |
| currency | String | `BRL` |
| createdAt | String | ISO timestamp |
| paidAt | String | ISO timestamp |
| metaJson | String | Dados extras do gateway | 5. Fluxos Autônomos (Tools)

O agente (`whats-agent`) recebe um conjunto de tools e decide **autonomamente** quando chamar cada uma. Não há lógica programática (if/else) controlando o fluxo — o LLM raciocina e age.

**Tools disponíveis para o Patient Agent:**

| Tool | Descrição |
|------|-----------|
| `calendar_search` | Consulta slots livres no Google Calendar |
| `calendar_book` | Cria o evento na agenda e retorna o `appointment_id` |
| `payment_generate` | Gera link de pagamento no gateway (Mercado Pago/PagSeguro). O agente chama esta tool **após** o paciente confirmar o horário |
| `rag_retriever` | Busca exemplos de conversas no JSON de referência para few-shot |
| `notify_nutri` | Encaminha dúvidas clínicas para o WhatsApp da Nutricionista |

> **Importante:** `calendar_search`, `calendar_book` e `payment_generate` são chamadas diretamente dentro do `whats-agent`. Não existe uma Lambda separada de `calendar-agent`. O agente possui as credenciais e chama a API do Google Calendar e do gateway de pagamento diretamente por meio das tools.

**Lambda `payment-webhook` (sem agent):**
Recebe o evento do gateway (Mercado Pago/PagSeguro), valida a assinatura, atualiza o status no DynamoDB (`Appointments.paymentStatus = paid`, `status = confirmed`) e envia notificação ao paciente via WhatsApp. Lógica 100% determinística, sem LLM.6. Lógica de Hibernação e RouterRouter Lógico (Zero Tokens): Se from == NUTRI_PHONE, carrega o Grafo Admin; caso contrário, Grafo Paciente.+2Hibernação: Se o message-buffer detectar uma mensagem da Nutri (is_echo: true), trava o agente por 10 minutos (seta hibernation_until no DynamoDB). O agente deve checar este campo antes de qualquer execução.7. Custos Mensais (100 Agendamentos/Mês)ServiçoCusto Est. (us-east-1)AWS Lambda$0.00 (Free Tier)DynamoDB$0.50 (On-demand) API Gateway$1.00Gemini 1.5 Flash$3.00 - $7.00 (Incluindo tokens do RAG)WhatsApp APIGrátis (Free tier da Meta) Total**~$5.00 a $10.00 USD**8. Critérios de AceiteAutonomia: O agente deve decidir sozinho se precisa perguntar o nome, oferecer um horário ou enviar o link de pagamento.+2RAG: As respostas devem refletir o estilo de escrita presente no arquivo de exemplos.Pagamento: A consulta só muda para o status CONFIRMED após o webhook de pagamento aprovado.+2Resiliência: Se o Google Calendar estiver fora, o agente deve informar o paciente de forma humana ("Tive um probleminha para acessar a agenda agora, pode me chamar em 5 minutos?").9. Estrutura de Projeto Simplificada

```
├── src/
│   ├── shared/                    # Código compartilhado entre Lambdas
│   │   ├── config.py              # Configurações e variáveis de ambiente
│   │   ├── db.py                  # Cliente DynamoDB (3 tabelas)
│   │   ├── whatsapp.py            # Cliente WhatsApp Cloud API
│   │   └── utils.py               # Utilitários gerais
│   │
│   ├── functions/                 # Lambdas (cada uma auto-contida)
│   │   ├── message_buffer/        # Agrega mensagens (2 min)
│   │   │   └── handler.py
│   │   │
│   │   ├── whats_agent/           # Agent principal (LangGraph)
│   │   │   ├── handler.py         # Entry point
│   │   │   ├── agents/            # Patient Agent, Nutri Agent
│   │   │   │   ├── patient.py
│   │   │   │   └── nutri.py
│   │   │   ├── tools/             # Ferramentas do agent
│   │   │   │   ├── calendar.py
│   │   │   │   ├── payment.py
│   │   │   │   └── rag.py         # RAG retriever
│   │   │   └── data/
│   │   │       └── examples.json  # Diálogos para RAG
│   │   │
│   │   └── payment_webhook/       # Processa webhooks de pagamento (sem agent)
│   │       └── handler.py
│   │
│   └── requirements.txt           # Dependências Python
│
├── infra/
│   └── template.yaml              # AWS SAM (API Gateway + Lambdas + DynamoDB)
│
├── .github/
│   └── workflows/
│       └── deploy.yaml            # CI/CD
│
└── docs/
    ├── PRD.md                     # Este documento
    ├── ARCHITECTURE.md            # Diagramas de arquitetura
    └── SETUP.md                   # Guia de deploy
```

**Princípios da Estrutura:**
- **src/shared**: Código reutilizável (evita duplicação)
- **src/functions**: Cada Lambda é independente mas usa shared
- **Flat structure**: Máximo 3 níveis de profundidade
- **Nomenclatura clara**: Nome da pasta = nome da função
- **Sem Lambda de calendar**: o Google Calendar é acessado diretamente pelas tools dentro do `whats-agent`
- **payment-webhook é simples**: não tem LLM, apenas recebe o evento, persiste no DynamoDB e notifica o paciente
10. Instruções de Deploy (CI/CD)GitHub Secrets: Configurar AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, NUTRI_PHONE_NUMBER.SAM Deploy: O workflow deve rodar sam build e sam deploy na região us-east-1 a cada push na main.Arquivo de Exemplo RAG (examples.json)A IA de desenvolvimento deve criar este arquivo para alimentar o RAG:JSON[
  {
    "context": "Paciente querendo marcar consulta pela primeira vez",
    "dialogue": "Paciente: Oi, quero marcar.\nAgente: Olá! Que alegria seu interesse. Para começarmos, qual seu nome completo e o que te traz à Dra. Ana hoje?"
  },
  {
    "context": "Paciente achou o preço caro",
    "dialogue": "Paciente: Achei caro.\nAgente: Entendo perfeitamente. O valor da Dra. Ana reflete o acompanhamento 24h e o plano personalizado. Queremos muito te ajudar, gostaria de ver uma opção de parcelamento?"
  }
]