# 01 product search

Execution mode: deterministic offline demo (NOT an LLM transcript).
Executed through Agent, validated tools, SQLite and PDF retrieval.
Dataset: published sanitized CSV snapshot. No external live service was queried.

**Customer:** Quais violões disponíveis custando até R$1000?

**Agent:** Encontrei estas opções na base fornecida:

- Tagima Memphis AC-39 Nylon Natural: R$ 429,90; 15 unidade(s) no arquivo.
- Rozini RC-104 Nylon Estudante: R$ 459,90; 10 unidade(s) no arquivo.
- Shelby SN-100 Folk Aço Preto: R$ 549,00; 5 unidade(s) no arquivo.
- Giannini GF-1R Aço Folk Sunburst: R$ 579,90; 7 unidade(s) no arquivo.
- Yamaha C40 Nylon Natural: R$ 599,90; 12 unidade(s) no arquivo.
- Giannini GN-15 Nylon Cedr Natural: R$ 689,00; 6 unidade(s) no arquivo.
- Yamaha F310 Aço Natural: R$ 699,90; 14 unidade(s) no arquivo.
- Tagima Dallas Tuner Aço Natural: R$ 749,00; 9 unidade(s) no arquivo.
- Shelby SGD-195E Elétrico Aço Sunburst: R$ 799,00; 6 unidade(s) no arquivo.
- Yamaha C70 Nylon Natural: R$ 849,00; 8 unidade(s) no arquivo.
- Tagima Woodstock Dreadnought Natural: R$ 899,00; 11 unidade(s) no arquivo.
- Tagima TW-7 7 Cordas Aço Natural: R$ 999,00; 6 unidade(s) no arquivo.

Estoque e preços são do arquivo, sem atualização ao vivo.

Tool execution:

```json
[
  {
    "evidence_id": "e1",
    "tool": "search_products",
    "arguments": {
      "query": null,
      "category": "Violões",
      "min_price_brl": null,
      "max_price_brl": 1000,
      "available_only": true,
      "limit": 20
    },
    "summary": {
      "product_ids": [
        83,
        85,
        89,
        88,
        81,
        84,
        87,
        86,
        107,
        82,
        91,
        112
      ],
      "total_matches": 12
    }
  }
]
```
