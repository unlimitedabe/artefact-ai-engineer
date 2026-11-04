# 05 verified order

Execution mode: deterministic offline demo (NOT an LLM transcript).
Executed through Agent, validated tools, SQLite and PDF retrieval.
Dataset: published sanitized CSV snapshot. No external live service was queried.

Precondition: synthetic customer verified outside chat with `customer03@example.invalid` and phone `00000000003`. This is a demonstration identity, not production authentication.

**Customer:** Qual o status do pedido 1?

**Agent:** O pedido 1 está entregue no arquivo fornecido. Total registrado: R$ 11.499,00. Rastreio demonstrativo: DEMO000000001. A base é estática; não confirma atualizações posteriores nem recebimento real.

Tool execution:

```json
[
  {
    "evidence_id": "e1",
    "tool": "get_order_status",
    "arguments": {
      "order_id": 1
    },
    "summary": {
      "order_id": 1,
      "status": "delivered",
      "total_cents": 1149900
    }
  }
]
```

**Customer:** Qual o status do pedido 2?

**Agent:** Não encontrei esse pedido para o cliente verificado. Confira o número.

Tool execution:

```json
[
  {
    "evidence_id": "e1",
    "tool": "get_order_status",
    "arguments": {
      "order_id": 2
    },
    "summary": {
      "error": "order_not_found_for_verified_customer"
    }
  }
]
```
