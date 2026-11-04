import sqlite3

import pytest

from emporio.session import Verification
from emporio.tools import Tools, tool_definitions


def search(tools, **overrides):
    params = dict(
        query=None,
        category=None,
        min_price_brl=None,
        max_price_brl=None,
        available_only=True,
        limit=20,
    )
    return tools.execute("search_products", params | overrides)


def test_available_guitars_under_thousand(tools):
    result = search(tools, category="Violões", max_price_brl=1000)
    assert result["total_matches"] == 12
    assert all(p["available"] and p["price_cents"] <= 100000 for p in result["products"])
    assert result["products"][0]["name"] == "Tagima Memphis AC-39 Nylon Natural"
    assert result["products"][0]["price"] == "R$ 429,90"


def test_name_accents_and_inclusive_price_filter(tools):
    result = search(tools, query="Takamine GD20", min_price_brl=2199, max_price_brl=2199)
    assert len(result["products"]) == 1
    assert result["products"][0]["price_cents"] == 219900
    assert search(tools, category="violao")["total_matches"] > 0


@pytest.mark.parametrize("product_id", [96, 113, 130, 136])
def test_availability_requires_active_and_positive_stock(tools, product_id):
    product = tools.execute("get_product_details", {"product_id": product_id})
    assert product["available"] is False
    if product_id in (130, 136):
        assert product["stock_quantity"] > 0


def test_lifecycle_status_excluded_even_with_positive_stock(tools):
    all_products = search(tools, available_only=False)["products"]
    for product in all_products:
        if product["status"] != "active":
            assert product["available"] is False
    result = search(tools, query="GF-3D")
    assert result["products"] == []


def test_promotions_actual_active_flags_and_exact_arithmetic(tools):
    result = tools.execute("get_promotions", {"product_id": None})
    assert {p["product_id"] for p in result["products"]} == {90, 94, 121, 127}
    product = tools.execute("get_product_details", {"product_id": 90})
    assert product["list_price_cents"] == 239900
    assert product["price_cents"] == 196718
    assert product["promotion"]["discount_percent"] == 18
    assert product["promotion_dates"] is None
    assert tools.execute("get_promotions", {"product_id": 93})["products"] == []


def test_quote_pix_not_cumulative_and_credit_sum_exact(tools):
    quote = tools.execute(
        "quote_product", dict(product_id=90, payment_method="pix", installments=1)
    )
    assert quote["total_cents"] == 196718 and not quote["pix_discount_applied"]
    quote = tools.execute(
        "quote_product", dict(product_id=95, payment_method="pix", installments=1)
    )
    assert quote["total_cents"] == 208905 and quote["pix_discount_applied"]
    quote = tools.execute(
        "quote_product", dict(product_id=90, payment_method="credit", installments=12)
    )
    assert len(quote["installment_schedule"]) == 12
    assert quote["installment_schedule"].count("R$ 163,94") == 2
    assert quote["installment_schedule"].count("R$ 163,93") == 10


def test_installment_rules_reject_small_installments(tools):
    result = tools.execute(
        "quote_product", dict(product_id=83, payment_method="credit", installments=12)
    )
    assert result["error"] == "installment_below_manual_minimum"
    assert (
        tools.execute("quote_product", dict(product_id=83, payment_method="pix", installments=2))[
            "error"
        ]
        == "installments_require_credit"
    )


def test_identity_and_cross_customer_order_scope(store, policies):
    assert store.verify_customer("CUSTOMER03@example.invalid", "00000000003") == 3
    assert store.verify_customer("customer03@example.invalid", "99999999999") is None
    assert store.verify_customer("nobody@example.invalid", "00000000003") is None
    assert (
        Tools(store, policies).execute("get_order_status", {"order_id": 1})["error"]
        == "identity_required"
    )
    tools = Tools(store, policies, customer_id=3)
    order = tools.execute("get_order_status", {"order_id": 1})
    assert order["status"] == "delivered" and order["total_cents"] == 1149900
    assert order["received_at"] is None and order["sales_channel"] is None
    assert "customer_id" not in order and "email" not in order
    assert tools.execute("get_order_status", {"order_id": 2}) == tools.execute(
        "get_order_status", {"order_id": 999}
    )


def test_customer_cannot_be_set_by_tool_arguments(tools):
    result = tools.execute("get_order_status", {"order_id": 1, "customer_id": 3})
    assert result["error"] == "invalid_arguments"
    assert all("customer_id" not in t["parameters"]["properties"] for t in tool_definitions())


def test_verification_attempt_limit_and_reset(store):
    session = Verification()
    for _ in range(5):
        assert not session.verify(store, "wrong@example.invalid", "11111111111")
    assert not session.verify(store, "customer03@example.invalid", "00000000003")
    assert session.customer_id is None


@pytest.mark.parametrize(
    "name,args",
    [
        ("search_products", {"query": "test"}),  # Missing required nullable fields.
        ("get_product_details", {"product_id": -1}),
        ("get_product_details", {"product_id": True}),
        ("get_order_status", {"order_id": "1"}),
        ("get_promotions", {"product_id": 0}),
        ("get_order_status", "not-json"),
        ("get_order_status", "[]"),
        (
            "assess_return_request",
            {
                "channel": "online",
                "received_on": "not-a-date",
                "original_packaging": True,
                "unused_complete": True,
                "special_item": False,
            },
        ),
    ],
)
def test_invalid_arguments_are_safe(tools, name, args):
    assert tools.execute(name, args)["error"] == "invalid_arguments"


def test_invalid_price_range_and_precision(tools):
    assert search(tools, min_price_brl=10, max_price_brl=9)["error"] == "invalid_arguments"
    assert search(tools, max_price_brl=1.001)["error"] == "invalid_arguments"


def test_no_sql_execution_and_database_is_read_only(tools, store):
    assert tools.execute("execute_sql", {"query": "DROP TABLE products"})["error"] == "unknown_tool"
    assert search(tools, query="zzzz' OR 1=1 --")["products"] == []
    with store.connect() as db, pytest.raises(sqlite3.OperationalError):
        db.execute("DELETE FROM products")
    assert search(tools, query="Yamaha C40")["products"]


def test_missing_product_and_empty_search(tools):
    assert tools.execute("get_product_details", {"product_id": 999})["error"] == "product_not_found"
    assert search(tools, query="instrumento inexistente")["products"] == []
