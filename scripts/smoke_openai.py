"""Opt-in paid smoke check. Never silently substitutes offline responses."""

import json
from pathlib import Path

from emporio.bootstrap import create_agent, resources
from emporio.config import Settings


def main():
    settings = Settings.from_env()
    if not settings.api_key:
        print("NOT RUN: OPENAI_API_KEY is absent. No real model validation was performed.")
        return 2
    # This smoke test deliberately uses only sanitized public records.
    settings.data_dir = Path("fixtures/public")
    settings.database_path = Path("runtime/smoke.sqlite3")
    settings.mode = "openai"
    store, policies = resources(settings)
    agent = create_agent(settings, store, policies)
    failures = 0
    for question, expected_tool in [
        ("Quanto custa o Takamine GD20?", "search_products"),
        ("E ele no PIX?", "quote_product"),
        ("Comprei online e recebi há três dias. Posso devolver?", "search_store_policies"),
    ]:
        result = agent.reply(question)
        used = [entry["tool"] for entry in result.trace]
        # Alternative valid policy route is accepted; no keyword-only response success claim.
        valid = result.status == "ok" and (
            expected_tool in used
            or (expected_tool == "search_store_policies" and "assess_return_request" in used)
        )
        failures += not valid
        print(
            json.dumps(
                {
                    "question": question,
                    "answer": result.answer,
                    "tools": used,
                    "status": result.status,
                    "tool_check_passed": valid,
                },
                ensure_ascii=False,
            )
        )
    print(
        f"Real API smoke: {3 - failures} passed, {failures} failed. "
        "Review answer grounding and language manually before submission."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
