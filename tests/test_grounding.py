from emporio.agent import allowed_amounts


def test_money_grounding_accepts_equivalent_brazilian_formatting():
    assert allowed_amounts({"text": "R$500 e R$ 500,00"}) == {50000}
    assert allowed_amounts({"text": "Custa R$ 2.089,05."}) == {208905}
    assert allowed_amounts({"text": "R$ 0,00 e R$ 1.000"}) == {0, 100000}
    assert allowed_amounts({"text": "R$ ... ainda não confirmado"}) == set()
