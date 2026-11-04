from datetime import date

import pytest

from emporio.policies import return_precheck


@pytest.mark.parametrize(
    "query,section",
    [
        ("Qual o horário de funcionamento?", "2"),
        ("What are your opening hours?", "2"),
        ("Qual o endereço?", "1.2"),
        ("Where is your store located? address", "1.2"),
        ("Quero devolver minha compra", "4.1"),
        ("Return my online purchase", "4.1"),
        ("Posso acumular desconto PIX?", "6.2"),
        ("Regras de parcelamento", "3.1"),
        ("garantia legal", "8.1"),
    ],
)
def test_relevant_section_in_top_results(policies, query, section):
    assert section in [r["section"] for r in policies.search(query)["matches"]]


def test_returns_always_retrieve_special_item_conditions(policies):
    matches = policies.search("arrependimento", limit=1)["matches"]
    assert {"4.1", "4.4"}.issubset({r["section"] for r in matches})
    assert all(r["pages"] == [4] for r in matches)
    text = " ".join(r["text"] for r in matches)
    assert "7 (sete) dias corridos" in text and "10 dias úteis" in text


def test_sections_continue_across_pages(policies):
    chunk = policies.by_section["5.2"]
    assert chunk.pages == [4, 5]
    assert "SEDEX" in chunk.text and "Jadlog" in chunk.text
    assert policies.by_section["9"].pages == [7, 8]


def test_unknown_topic_has_no_matches(policies):
    assert policies.search("quantum xylophagous zzzzz")["matches"] == []


@pytest.mark.parametrize(
    "received,packaging,unused,special,expected",
    [
        ("2026-03-15", True, True, False, "within_manual_request_window"),
        ("2026-03-14", True, True, False, "outside_manual_regret_window"),
        (None, True, True, False, "missing_information"),
        ("2026-03-23", True, True, False, "invalid_receipt_date"),
        ("2026-03-20", None, True, False, "missing_information"),
        ("2026-03-20", True, False, False, "needs_team_review"),
        ("2026-03-20", True, True, True, "needs_team_review"),
    ],
)
def test_return_precheck_and_window_boundaries(received, packaging, unused, special, expected):
    result = return_precheck(
        channel="online",
        received_on=received,
        original_packaging=packaging,
        unused_complete=unused,
        special_item=special,
        today=date(2026, 3, 22),
    )
    assert result["assessment"] == expected
    assert result["approval"] is False
    assert "page 4" in result["source"]


def test_unknown_channel_not_inferred_from_order(tools):
    result = tools.execute(
        "assess_return_request",
        dict(
            channel="unknown",
            received_on=None,
            original_packaging=None,
            unused_complete=None,
            special_item=None,
        ),
    )
    assert result["assessment"] == "needs_team_review"
    assert result["approval"] is False
    assert result["policy"]["matches"]
