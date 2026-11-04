"""Bounded tool loop with per-session memory and evidence-gated answers."""

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from emporio.prompts import SYSTEM_PROMPT
from emporio.provider import Provider, ProviderError
from emporio.tools import Tools, tool_definitions


class FinalReply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str = Field(min_length=1, max_length=12000)
    kind: str = Field(pattern="^(store_answer|clarification|out_of_scope|greeting)$")
    evidence_ids: list[str]


@dataclass
class TurnResult:
    answer: str
    trace: list[dict] = field(default_factory=list)
    status: str = "ok"


FALLBACK = (
    "Não consegui confirmar uma resposta com segurança agora. "
    "Tente reformular a pergunta ou peça uma conferência à equipe da loja."
)


def allowed_amounts(evidence: dict) -> set[int]:
    """Reject BRL amounts absent from tool evidence, including PDF policy excerpts."""
    text = json.dumps(evidence, ensure_ascii=False)
    # Accept equivalent Brazilian display forms, including R$500 versus R$ 500,00.
    amounts = set()
    for match in re.findall(r"R\$\s*(\d[\d.]*(?:,\d{2})?)", text):
        whole, _, fraction = match.rstrip(".").partition(",")
        amounts.add(int(whole.replace(".", "")) * 100 + int(fraction or "0"))
    return amounts


class Agent:
    def __init__(
        self, provider: Provider, tools: Tools, max_rounds: int = 5, history_turns: int = 8
    ):
        self.provider, self.tools = provider, tools
        self.max_rounds, self.history_turns = max_rounds, history_turns
        # Keep whole turns together; never retain an orphan function-call output.
        self.turns: list[list[dict]] = []

    def reply(self, user_text: str) -> TurnResult:
        if not user_text.strip() or len(user_text) > 4000:
            return TurnResult(
                "Envie uma mensagem entre 1 e 4.000 caracteres.", status="invalid_input"
            )
        history = deepcopy([m for turn in self.turns[-self.history_turns :] for m in turn])
        current = [{"role": "user", "content": user_text}]
        trace, evidence = [], {}
        instructions = SYSTEM_PROMPT + f"\nData local da loja: {self.tools.today.isoformat()}."
        try:
            for _ in range(self.max_rounds):
                response = self.provider.respond(
                    instructions, history + current, tool_definitions()
                )
                calls = [item for item in response.output if item.get("type") == "function_call"]
                if calls:
                    if len(calls) > 8:
                        return TurnResult(FALLBACK, trace, "tool_limit")
                    # Preserve all items, including reasoning items required by reasoning models.
                    current.extend(response.output)
                    for call in calls:
                        result = self.tools.execute(call.get("name", ""), call.get("arguments", ""))
                        evidence_id = f"e{len(trace) + 1}"
                        evidence[evidence_id] = result
                        trace.append(
                            {
                                "evidence_id": evidence_id,
                                "tool": call.get("name"),
                                "arguments": call.get("arguments"),
                                "result": result,
                            }
                        )
                        current.append(
                            {
                                "type": "function_call_output",
                                "call_id": call["call_id"],
                                "output": json.dumps(
                                    {"evidence_id": evidence_id, "data": result}, ensure_ascii=False
                                ),
                            }
                        )
                    continue
                try:
                    final = FinalReply.model_validate_json(response.text)
                except ValueError:
                    current.append(
                        {"role": "developer", "content": "Return valid customer_reply JSON."}
                    )
                    continue
                used = {key: evidence[key] for key in final.evidence_ids if key in evidence}
                valid_evidence = bool(used) and len(used) == len(set(final.evidence_ids))
                successful = any("error" not in value for value in used.values())
                amounts = allowed_amounts(used)
                output_amounts = allowed_amounts({"answer": final.answer})
                ungrounded = final.kind == "store_answer" and not (valid_evidence and successful)
                if ungrounded or not output_amounts.issubset(amounts):
                    current.append(
                        {
                            "role": "developer",
                            "content": (
                                "Answer was rejected: obtain current-turn evidence with tools. "
                                "All money amounts must occur in evidence; use quote_product "
                                "for calculations. If data unavailable, ask clarification "
                                "without asserting store facts."
                            ),
                        }
                    )
                    continue
                current.append({"role": "assistant", "content": response.text})
                self.turns.append(current)
                self.turns = self.turns[-self.history_turns :]
                return TurnResult(final.answer, trace)
        except ProviderError:
            return TurnResult(
                "O serviço de IA está indisponível. Confira a chave, o acesso ao modelo e os "
                "créditos da API, ou tente novamente mais tarde.",
                trace,
                "provider_error",
            )
        return TurnResult(FALLBACK, trace, "grounding_or_round_limit")
