# Máquina de Estados (MVP)

## Objetivo
Definir transições seguras para conversa e domínio de agendamento/pagamento, separando decisão conversacional (LLM) de confirmação crítica (determinística).

## 1) Máquina de Conversa

```mermaid
stateDiagram-v2
    [*] --> ACTIVE
    ACTIVE --> HANDOFF_HUMAN: mensagem da nutri / comando handoff
    HANDOFF_HUMAN --> ACTIVE: /ia on ou expiração hibernação

    ACTIVE --> QUALIFYING: intenção = agendar
    QUALIFYING --> OFFERING_SLOTS: dados mínimos ok
    OFFERING_SLOTS --> WAIT_SLOT_CONFIRM: slots enviados
    WAIT_SLOT_CONFIRM --> BOOKING: paciente confirma horário
    BOOKING --> WAIT_PAYMENT: calendar_book sucesso + link enviado
    WAIT_PAYMENT --> CONFIRMED: payment.confirmed webhook
    WAIT_PAYMENT --> PAYMENT_EXPIRED: timeout (ex 24h)

    ACTIVE --> RESCHEDULE_FLOW: intenção = remarcar
    RESCHEDULE_FLOW --> WAIT_PAYMENT: novo slot reservado + pagamento pendente
    RESCHEDULE_FLOW --> CONFIRMED: isenção de novo pagamento (regra)

    ACTIVE --> CANCEL_FLOW: intenção = cancelar
    CANCEL_FLOW --> CANCELED: cancelamento concluído

    CONFIRMED --> [*]
    CANCELED --> [*]
    PAYMENT_EXPIRED --> ACTIVE
```

## 2) Máquina de Domínio (Agendamento/Pagamento)

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> SLOT_HELD: slot reservado no calendário
    SLOT_HELD --> PAYMENT_PENDING: link de pagamento gerado
    PAYMENT_PENDING --> CONFIRMED: webhook aprovado
    PAYMENT_PENDING --> EXPIRED: timeout de pagamento
    SLOT_HELD --> CANCELED: desistência
    CONFIRMED --> RESCHEDULE_PENDING: solicitação de remarcação
    RESCHEDULE_PENDING --> CONFIRMED: novo slot confirmado
    CONFIRMED --> CANCELED: cancelamento
```

## Guardrails Obrigatórios
1. `CONFIRMED` só pode ser definido após evento válido de `payment-webhook`.
2. `calendar_book` só executa quando houver `slot_id` retornado por `calendar_search`.
3. Em `HANDOFF_HUMAN`, respostas automáticas ficam bloqueadas até comando de retorno.
4. Em timeout de pagamento, transição para `EXPIRED` e liberação de slot (se política exigir).

## Regras de Negócio Mínimas
- `slot_hold_ttl_minutes`: 15
- `payment_ttl_hours`: 24
- `max_reschedules`: 1 (MVP, configurável)
- Cancelamento com reembolso depende da política da clínica e gateway.
