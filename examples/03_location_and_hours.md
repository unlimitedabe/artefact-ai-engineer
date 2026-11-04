# 03 location and hours

Execution mode: deterministic offline demo (NOT an LLM transcript).
Executed through Agent, validated tools, SQLite and PDF retrieval.
Dataset: published sanitized CSV snapshot. No external live service was queried.

**Customer:** Qual o endereço da loja?

**Agent:** O endereço é Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333. [Manual, seção 1.2, página 2.]

Tool execution:

```json
[
  {
    "evidence_id": "e1",
    "tool": "search_store_policies",
    "arguments": {
      "query": "Qual o endereço da loja?"
    },
    "summary": {
      "sections": [
        {
          "section": "1.2",
          "pages": [
            2
          ]
        },
        {
          "section": "2",
          "pages": [
            2
          ]
        },
        {
          "section": "9",
          "pages": [
            7,
            8
          ]
        },
        {
          "section": "6.1",
          "pages": [
            6
          ]
        },
        {
          "section": "3.1",
          "pages": [
            3
          ]
        },
        {
          "section": "6.2",
          "pages": [
            6
          ]
        }
      ]
    }
  }
]
```

**Customer:** Qual o horário de funcionamento?

**Agent:** O manual informa:

2. Horário de Funcionamento
O atendimento presencial na loja segue os horários abaixo. O atendimento via WhatsApp segue o
mesmo horário, com respostas automáticas fora do expediente.
Dia Horário
Segunda a Sexta-feira 09:00 às 18:00
Sábado 09:00 às 13:00
Domingo e Feriados Fechado
Em datas especiais (Black Friday, Aniversário da Loja, Natal), o horário pode ser estendido.
Alterações serão comunicadas com antecedência nas redes sociais e no atendimento via WhatsApp.

[Manual, seção 2, página 2.]

Tool execution:

```json
[
  {
    "evidence_id": "e1",
    "tool": "search_store_policies",
    "arguments": {
      "query": "Qual o horário de funcionamento?"
    },
    "summary": {
      "sections": [
        {
          "section": "2",
          "pages": [
            2
          ]
        },
        {
          "section": "7.1",
          "pages": [
            6
          ]
        }
      ]
    }
  }
]
```
