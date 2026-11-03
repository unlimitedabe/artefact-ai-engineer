"""Explicitly limited offline demonstration, not an LLM or a substitute for model validation."""

import json
import re

from emporio.provider import ModelResponse
from emporio.text import normalize


class DemoProvider:
    """Deterministic router for the documented example scenarios; uses real application tools."""

    @staticmethod
    def call(name: str, params: dict) -> ModelResponse:
        return ModelResponse(
            [
                {
                    "type": "function_call",
                    "call_id": "demo_call",
                    "name": name,
                    "arguments": json.dumps(params, ensure_ascii=False),
                }
            ]
        )

    @staticmethod
    def final(answer: str, kind="store_answer", evidence_ids=None) -> ModelResponse:
        return ModelResponse(
            text=json.dumps(
                {"answer": answer, "kind": kind, "evidence_ids": evidence_ids or []},
                ensure_ascii=False,
            )
        )

    def respond(self, instructions: str, messages: list[dict], tools: list[dict]) -> ModelResponse:
        last_user = max(i for i, m in enumerate(messages) if m.get("role") == "user")
        text = normalize(messages[last_user]["content"])
        outputs = [
            json.loads(m["output"])
            for m in messages[last_user:]
            if m.get("type") == "function_call_output"
        ]
        if outputs:
            output = outputs[-1]
            data, eid = output["data"], [output["evidence_id"]]
            if "error" in data:
                answers = {
                    "identity_required": "Para consultar o pedido, confirme e-mail e telefone na "
                    "barra lateral (no terminal: /verify).",
                    "order_not_found_for_verified_customer": "Não encontrei esse pedido para o "
                    "cliente verificado. Confira o número.",
                }
                return self.final(
                    answers.get(data["error"], "Pode conferir os dados da solicitação?"),
                    "clarification",
                    eid,
                )
            if "order_id" in data:
                statuses = {
                    "delivered": "entregue",
                    "shipped": "enviado",
                    "confirmed": "confirmado",
                    "pending": "pendente",
                    "cancelled": "cancelado",
                }
                return self.final(
                    f"O pedido {data['order_id']} está {statuses[data['status']]} "
                    "no arquivo fornecido. "
                    f"Total registrado: {data['total']}. "
                    + (
                        f"Rastreio demonstrativo: {data['tracking_code']}. "
                        if data["tracking_code"]
                        else "O arquivo não informa rastreio. "
                    )
                    + "A base é estática; não confirma atualizações posteriores "
                    "nem recebimento real.",
                    evidence_ids=eid,
                )
            if "total_cents" in data:
                product = data["product"]
                campaign = product["promotion"]
                prefix = (
                    f"De {product['list_price']} por {product['price']} "
                    f"({campaign['discount_percent']}% de desconto). "
                    if campaign
                    else ""
                )
                return self.final(
                    prefix
                    + f"Para {product['name']}, a cotação no PIX é {data['total']}. "
                    + (
                        "O desconto de 5% foi aplicado ao preço de tabela."
                        if data["pix_discount_applied"]
                        else "A promoção não acumula os 5% de PIX."
                    )
                    + " [Manual, seções 3 e 6.2, páginas 3 e 6.] Cotação da base fornecida.",
                    evidence_ids=eid,
                )
            if "products" in data:
                products = data["products"]
                if not products:
                    return self.final(
                        "Não encontrei produtos com esses filtros na base fornecida.",
                        evidence_ids=eid,
                    )
                lines = []
                for product in products:
                    price = product["price"]
                    if product["promotion"]:
                        price = (
                            f"de {product['list_price']} por {price} "
                            f"({product['promotion']['discount_percent']}% de desconto)"
                        )
                    lines.append(
                        f"- {product['name']}: {price}; "
                        f"{product['stock_quantity']} unidade(s) no arquivo."
                    )
                notice = "\nHá mais resultados; refine a busca." if data.get("truncated") else ""
                return self.final(
                    "Encontrei estas opções na base fornecida:\n\n"
                    + "\n".join(lines)
                    + notice
                    + "\n\nEstoque e preços são do arquivo, sem atualização ao vivo.",
                    evidence_ids=eid,
                )
            if "matches" in data:
                matches = data["matches"]
                wanted = (
                    "4.1"
                    if any(w in text for w in ["devol", "arrepend", "return"])
                    else ("2" if any(w in text for w in ["horario", "hours", "abre"]) else "1.2")
                )
                chunk = next((c for c in matches if c["section"] == wanted), None)
                if chunk is None:
                    return self.final(
                        "A demonstração offline não cobre esta pergunta. "
                        "Pode tentar uma busca por horário, endereço ou devolução?",
                        "clarification",
                        eid,
                    )
                if wanted == "4.1":
                    answer = (
                        "Para compras online, o manual permite solicitar devolução "
                        "até 7 dias corridos após o recebimento, com embalagem original, "
                        "sem uso e com acessórios e manuais. O reembolso usa a forma "
                        "original de pagamento, em até 10 dias úteis, e o frete de devolução "
                        "por arrependimento é da loja. Itens personalizados, venda final e "
                        "boquilhas precisam de avaliação da equipe. "
                        "[Manual, seções 4.1 e 4.4, página 4.] "
                        "A compra foi online, quando você recebeu e como está o produto? "
                        "Esta orientação não aprova a devolução."
                    )
                elif wanted == "2":
                    answer = (
                        "O manual informa:\n\n" + chunk["text"] + "\n\n[Manual, seção 2, página 2.]"
                    )
                else:
                    answer = (
                        "O endereço é Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, "
                        "CEP 79202-333. [Manual, seção 1.2, página 2.]"
                    )
                return self.final(answer, evidence_ids=eid)
        if text.strip(" !.?") in {"oi", "ola", "hello", "obrigado", "obrigada"}:
            return self.final(
                "Olá! Como posso ajudar com instrumentos ou atendimento da loja?", "greeting"
            )
        if any(w in text for w in ["pedido", "order"]):
            match = re.search(r"(?:pedido|order)\s*#?\s*(\d+)", text)
            if match:
                return self.call("get_order_status", {"order_id": int(match[1])})
            return self.final("Qual é o número do pedido?", "clarification")
        if "pix" in text:
            previous = [
                json.loads(m["output"])["data"]
                for m in messages[:last_user]
                if m.get("type") == "function_call_output"
            ]
            for data in reversed(previous):
                products = data.get("products", [])
                if len(products) == 1:
                    return self.call(
                        "quote_product",
                        {
                            "product_id": products[0]["product_id"],
                            "payment_method": "pix",
                            "installments": 1,
                        },
                    )
            return self.final("De qual modelo você quer a cotação no PIX?", "clarification")
        if any(
            w in text for w in ["horario", "endereco", "devolver", "arrepend", "hours", "address"]
        ):
            return self.call("search_store_policies", {"query": messages[last_user]["content"]})
        if "viol" in text and any(w in text for w in ["1000", "1.000", "mil"]):
            return self.call(
                "search_products",
                {
                    "query": None,
                    "category": "Violões",
                    "min_price_brl": None,
                    "max_price_brl": 1000,
                    "available_only": True,
                    "limit": 20,
                },
            )
        for model in ["takamine gd20", "yamaha c40", "crafter ht-100"]:
            if model in text:
                return self.call(
                    "search_products",
                    {
                        "query": model,
                        "category": None,
                        "min_price_brl": None,
                        "max_price_brl": None,
                        "available_only": False,
                        "limit": 5,
                    },
                )
        return self.final(
            "Posso ajudar com instrumentos e atendimento da Empório da Música. "
            "Esta demonstração offline cobre buscas de violões até mil reais, "
            "preço do Takamine GD20, horário, endereço, devolução e consulta de pedido; "
            "para conversa livre, configure a API.",
            "out_of_scope",
        )
