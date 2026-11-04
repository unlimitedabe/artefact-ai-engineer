"""Explicit tool contracts; the model never receives SQL or identity-setting capabilities."""

import json
import sqlite3
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from emporio.policies import PolicyIndex, return_precheck
from emporio.store import Store
from emporio.text import brl, discounted, to_cents


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchProducts(Arguments):
    query: str | None = Field(..., max_length=150, description="Name terms, not a whole sentence")
    category: str | None = Field(..., max_length=80, description="Portuguese catalogue category")
    min_price_brl: float | None = Field(..., ge=0, le=1_000_000, allow_inf_nan=False)
    max_price_brl: float | None = Field(..., ge=0, le=1_000_000, allow_inf_nan=False)
    available_only: bool
    limit: int = Field(..., ge=1, le=20)

    @model_validator(mode="after")
    def price_range(self):
        if self.min_price_brl is not None and self.max_price_brl is not None:
            if self.min_price_brl > self.max_price_brl:
                raise ValueError("min_price_brl exceeds max_price_brl")
        return self


class ProductDetails(Arguments):
    product_id: int = Field(..., ge=1)


class Promotions(Arguments):
    product_id: int | None = Field(..., ge=1)


class OrderStatus(Arguments):
    order_id: int = Field(..., ge=1)


class SearchPolicies(Arguments):
    query: str = Field(..., min_length=2, max_length=400)


class ReturnCheck(Arguments):
    channel: Literal["online", "in_store", "unknown"]
    received_on: str | None = Field(
        ..., description="Actual receipt YYYY-MM-DD, never order estimate"
    )
    original_packaging: bool | None
    unused_complete: bool | None
    special_item: bool | None = Field(..., description="Customized, final-sale or mouthpiece")

    @model_validator(mode="after")
    def valid_date(self):
        if self.received_on is not None:
            date.fromisoformat(self.received_on)
        return self


class QuoteProduct(Arguments):
    product_id: int = Field(..., ge=1)
    payment_method: Literal["pix", "credit", "debit", "boleto"]
    installments: int = Field(..., ge=1, le=12)


CONTRACTS = {
    "search_products": (
        SearchProducts,
        "Search actual products by name/category/effective BRL "
        "price and availability. Use Portuguese category labels; do not include "
        "words like 'price' in query. For acoustic guitars use category Violões.",
    ),
    "get_product_details": (ProductDetails, "Get exact product price, specs, stock and campaign."),
    "get_order_status": (
        OrderStatus,
        "Read one order scoped to the verified UI/CLI customer. "
        "If identity_required, direct customer to sidebar or CLI /verify.",
    ),
    "get_promotions": (Promotions, "Get active, in-stock promotions from CSV; dates unavailable."),
    "search_store_policies": (
        SearchPolicies,
        "Retrieve authoritative policy sections with pages. "
        "Use for hours, location, payments, returns, warranty, scope, delivery.",
    ),
    "assess_return_request": (
        ReturnCheck,
        "Preliminary online-regret check using customer-provided "
        "facts. Null for unknown facts. Does not approve or issue refunds.",
    ),
    "quote_product": (
        QuoteProduct,
        "Calculate exact payment price from product and manual: "
        "5% PIX only without active campaign; no stacking; credit tier minimums. "
        "This is a quote, not a purchase.",
    ),
}


def tool_definitions() -> list[dict]:
    return [
        {
            "type": "function",
            "name": name,
            "description": description,
            "strict": True,
            "parameters": contract.model_json_schema(),
        }
        for name, (contract, description) in CONTRACTS.items()
    ]


class Tools:
    def __init__(
        self,
        store: Store,
        policies: PolicyIndex,
        customer_id: int | None = None,
        today: date | None = None,
    ):
        self.store = store
        self.policies = policies
        self._customer_id = customer_id
        # Store location is Campo Grande (not the developer's timezone).
        if today is None:
            from datetime import datetime
            from zoneinfo import ZoneInfo

            today = datetime.now(ZoneInfo("America/Campo_Grande")).date()
        self.today = today

    def execute(self, name: str, arguments: str | dict) -> dict:
        if name not in CONTRACTS:
            return {"error": "unknown_tool"}
        try:
            data = json.loads(arguments) if isinstance(arguments, str) else arguments
            if not isinstance(data, dict):
                return {"error": "invalid_arguments"}
            params = CONTRACTS[name][0].model_validate(data).model_dump()
            if name == "search_products":
                low, high = params.pop("min_price_brl"), params.pop("max_price_brl")
                return self.store.search_products(
                    **params,
                    min_price_cents=to_cents(str(low)) if low is not None else None,
                    max_price_cents=to_cents(str(high)) if high is not None else None,
                )
            if name == "get_product_details":
                return self.store.get_product_details(**params)
            if name == "get_promotions":
                return self.store.get_promotions(**params)
            if name == "get_order_status":
                return self.store.get_order_status(**params, customer_id=self._customer_id)
            if name == "search_store_policies":
                return self.policies.search(**params)
            if name == "assess_return_request":
                # Include source passages as evidence for both the model and the customer.
                return {
                    **return_precheck(**params, today=self.today),
                    "policy": self.policies.search("arrependimento devolução itens não elegíveis"),
                }
            if name == "quote_product":
                return self.quote(**params)
        except (ValidationError, ValueError, TypeError, ArithmeticError):
            # Do not echo exception/argument contents: they may contain credentials or PII.
            return {
                "error": "invalid_arguments",
                "instruction": "Use the tool's exact typed schema",
            }
        except sqlite3.Error:
            return {"error": "data_unavailable", "instruction": "Ask the store team; do not invent"}
        return {"error": "unknown_tool"}

    def quote(self, product_id: int, payment_method: str, installments: int) -> dict:
        product = self.store.get_product_details(product_id)
        if "error" in product:
            return product
        if not product["available"]:
            return {"error": "product_unavailable", "product": product}
        if payment_method != "credit" and installments != 1:
            return {"error": "installments_require_credit"}
        total = product["price_cents"]
        pix_applied = payment_method == "pix" and product["promotion"] is None
        if pix_applied:
            total = discounted(total, 5)
        if installments > 1:
            minimum = 5000 if installments <= 3 else (8000 if installments <= 6 else 10000)
            if total < minimum * installments:
                return {
                    "error": "installment_below_manual_minimum",
                    "minimum": brl(minimum),
                    "policy": self.policies.search("regras parcelamento"),
                }
        base, remainder = divmod(total, installments)
        return {
            "product": product,
            "payment_method": payment_method,
            "total_cents": total,
            "total": brl(total),
            "pix_discount_applied": pix_applied,
            "installments": installments,
            "installment_schedule": [
                brl(base + (1 if i < remainder else 0)) for i in range(installments)
            ],
            "policy": self.policies.search("pagamento pix regras parcelamento cumulatividade"),
            "notice": "Snapshot quote only; no stock reservation, purchase or payment performed",
        }
