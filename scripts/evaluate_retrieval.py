"""Small transparent retrieval diagnostic; no LLM or embedding API is called."""

import json
import math
from pathlib import Path

from emporio.policies import PolicyIndex
from emporio.text import tokens

CASES = [
    ("Qual o horário de funcionamento?", "2"),
    ("What are your opening hours?", "2"),
    ("Qual o endereço?", "1.2"),
    ("Where is your store? address", "1.2"),
    ("Quero devolver minha compra", "4.1"),
    ("Return my online purchase", "4.1"),
    ("Posso acumular desconto PIX?", "6.2"),
    ("Regras de parcelamento", "3.1"),
    ("garantia legal", "8.1"),
    ("frete para outras cidades", "5.2"),
    ("Código de rastreamento", "5.3"),
    ("acessórios amplificadores", "1"),
]


def evaluate():
    index = PolicyIndex(Path("data/políticas_da_loja.pdf"))
    results = []
    for query, expected in CASES:
        terms = set(tokens(query))
        overlap = sorted(
            zip(index.chunks, index.counters, strict=True),
            key=lambda pair: -len(terms & pair[1].keys()),
        )

        # TF-IDF cosine baseline: no bilingual aliases and no dependency expansion.
        def vector(counter):
            return {
                t: n * math.log((len(index.chunks) + 1) / (index.df[t] + 1)) + n
                for t, n in counter.items()
            }

        qv = vector({t: 1 for t in terms})

        def cosine(counter, query_vector=qv):
            dv = vector(counter)
            numerator = sum(query_vector[t] * dv.get(t, 0) for t in query_vector)
            denominator = math.sqrt(
                sum(v * v for v in query_vector.values()) * sum(v * v for v in dv.values())
            )
            return numerator / denominator if denominator else 0

        tfidf = sorted(
            zip(index.chunks, index.counters, strict=True), key=lambda pair: -cosine(pair[1])
        )
        bm25 = index.search(query, limit=3)["matches"][:3]
        results.append(
            {
                "query": query,
                "expected_section": expected,
                "overlap_hit_at_3": expected in [c.section for c, _ in overlap[:3]],
                "tfidf_hit_at_3": expected in [c.section for c, _ in tfidf[:3]],
                "bm25_alias_hit_at_3": expected in [c["section"] for c in bm25],
            }
        )
    return {
        "cases": len(CASES),
        "metric": "Expected-section hit@3 (not full precision/recall)",
        "scores": {
            key: sum(r[key] for r in results) / len(results)
            for key in ["overlap_hit_at_3", "tfidf_hit_at_3", "bm25_alias_hit_at_3"]
        },
        "details": results,
        "limitations": [
            "Author-constructed tiny diagnostic set; not a held-out benchmark.",
            "Aliases and queries were developed together; optimistic in-sample result.",
            "Embedding retrieval was considered conceptually, not executed.",
            "No measurement of live model tool selection or generated answer quality.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
