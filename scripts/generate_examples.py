"""Record five executed offline conversations through the real agent/tool loop."""

import json
from pathlib import Path

from emporio.bootstrap import create_agent, resources
from emporio.config import Settings

SCENARIOS = [
    ("01_product_search", ["Quais violões disponíveis custando até R$1000?"], None),
    ("02_price_and_pix", ["Quanto custa o Takamine GD20?", "E ele no PIX?"], None),
    (
        "03_location_and_hours",
        ["Qual o endereço da loja?", "Qual o horário de funcionamento?"],
        None,
    ),
    ("04_return_policy", ["Me arrependi da minha compra, posso devolver?"], None),
    ("05_verified_order", ["Qual o status do pedido 1?", "Qual o status do pedido 2?"], 3),
]


def generate(destination=Path("examples")):
    settings = Settings(mode="demo")
    store, policies = resources(settings)
    destination.mkdir(exist_ok=True)
    for name, questions, customer_id in SCENARIOS:
        content = [
            f"# {name.replace('_', ' ')}",
            "",
            "Execution mode: deterministic offline demo (NOT an LLM transcript).",
            "Executed through Agent, validated tools, SQLite and PDF retrieval.",
            "Dataset: published sanitized CSV snapshot. No external live service was queried.",
            "",
        ]
        if customer_id:
            assert store.verify_customer("customer03@example.invalid", "00000000003") == customer_id
            content += [
                "Precondition: synthetic customer verified outside chat with "
                "`customer03@example.invalid` and phone `00000000003`. "
                "This is a demonstration identity, not production authentication.",
                "",
            ]
        agent = create_agent(settings, store, policies, customer_id)
        for question in questions:
            result = agent.reply(question)
            if result.status != "ok":
                raise RuntimeError(f"Scenario failed: {name}: {result.status}")
            content += [
                f"**Customer:** {question}",
                "",
                f"**Agent:** {result.answer}",
                "",
                "Tool execution:",
                "",
                "```json",
            ]
            trace = [
                {
                    "evidence_id": t["evidence_id"],
                    "tool": t["tool"],
                    "arguments": json.loads(t["arguments"]),
                    "summary": summarize(t["result"]),
                }
                for t in result.trace
            ]
            content += [json.dumps(trace, ensure_ascii=False, indent=2), "```", ""]
        (destination / f"{name}.md").write_text("\n".join(content), encoding="utf-8")
    print(f"Recorded {len(SCENARIOS)} executed offline conversations in {destination}")


def summarize(data):
    if "products" in data:
        return {
            "product_ids": [p["product_id"] for p in data["products"]],
            "total_matches": data.get("total_matches", len(data["products"])),
        }
    if "matches" in data:
        return {
            "sections": [{"section": m["section"], "pages": m["pages"]} for m in data["matches"]]
        }
    if "total_cents" in data and "product" in data:
        return {
            "total_cents": data["total_cents"],
            "pix_discount_applied": data["pix_discount_applied"],
        }
    if "order_id" in data:
        return {
            "order_id": data["order_id"],
            "status": data["status"],
            "total_cents": data["total_cents"],
        }
    return data


if __name__ == "__main__":
    generate()
