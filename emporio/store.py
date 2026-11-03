"""Read-only, parameterized operational queries and session-bound customer verification."""

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from emporio.text import brl, discounted, normalize, tokens


class Store:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.create_function("normalize", 1, normalize, deterministic=True)
        db.execute("PRAGMA query_only=ON")
        try:
            yield db
        finally:
            db.close()

    def verify_customer(self, email: str, phone: str) -> int | None:
        """Called by UI/CLI only. The model cannot set or change authenticated identity."""
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 13 and digits.startswith("55"):
            digits = digits[2:]
        with self.connect() as db:
            rows = db.execute("SELECT customer_id, phone FROM customers WHERE email=?",
                              (email.strip().casefold(),)).fetchall()
        if len(rows) != 1:
            return None
        recorded = rows[0]["phone"]
        if len(recorded) == 13 and recorded.startswith("55"):
            recorded = recorded[2:]
        return rows[0]["customer_id"] if digits and digits == recorded else None

    @staticmethod
    def product(db: sqlite3.Connection, row: sqlite3.Row) -> dict:
        promotions = db.execute(
            "SELECT promotion_id, discount_percent, description FROM promotions "
            "WHERE product_id=? AND is_active=1 ORDER BY discount_percent DESC, promotion_id",
            (row["product_id"],),
        ).fetchall()
        available = row["status"] == "active" and row["stock_quantity"] > 0
        # Campaigns are not cumulative. Show the best active discount only when purchasable.
        best = promotions[0] if promotions and available else None
        price = discounted(row["price_cents"], best["discount_percent"]) if best else row["price_cents"]
        return {
            "product_id": row["product_id"], "name": row["name"], "category": row["category"],
            "description": row["description"], "specs": json.loads(row["specs"]),
            "status": row["status"], "stock_quantity": row["stock_quantity"], "available": available,
            "list_price_cents": row["price_cents"], "list_price": brl(row["price_cents"]),
            "price_cents": price, "price": brl(price),
            "promotion": dict(best) if best else None,
            "promotion_dates": None, "source": "CSV snapshot (not a live inventory service)",
        }

    def search_products(self, query: str | None, category: str | None,
                        min_price_cents: int | None, max_price_cents: int | None,
                        available_only: bool, limit: int) -> dict:
        clauses, params = [], []
        # Tokens are escaped for LIKE. All predicates and limit values are parameterized.
        if query:
            for token in tokens(query):
                clauses.append("normalize(p.name || ' ' || p.description) LIKE ?")
                params.append(f"%{token}%")
        if category:
            clauses.append("instr(normalize(c.name),?)>0")
            # Portuguese irregular plural; the other labels match by prefix.
            params.append({"violao": "violo", "violoes": "violo"}.get(
                normalize(category), normalize(category).rstrip("s")))
        if available_only:
            clauses.append("p.status='active' AND p.stock_quantity>0")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            rows = db.execute(
                "SELECT p.*,c.name AS category FROM products p JOIN categories c USING(category_id)"
                + where, params,
            ).fetchall()
            results = [self.product(db, row) for row in rows]
        results = [p for p in results
                   if (min_price_cents is None or p["price_cents"] >= min_price_cents)
                   and (max_price_cents is None or p["price_cents"] <= max_price_cents)]
        results.sort(key=lambda p: (p["price_cents"], p["product_id"]))
        return {"products": results[:limit], "total_matches": len(results),
                "truncated": len(results) > limit, "price_filter": "effective snapshot price"}

    def get_product_details(self, product_id: int) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT p.*,c.name AS category FROM products p JOIN categories c USING(category_id) "
                "WHERE p.product_id=?", (product_id,),
            ).fetchone()
            return self.product(db, row) if row else {"error": "product_not_found"}

    def get_promotions(self, product_id: int | None) -> dict:
        with self.connect() as db:
            rows = db.execute(
                "SELECT DISTINCT p.*,c.name AS category FROM products p "
                "JOIN categories c USING(category_id) JOIN promotions pr USING(product_id) "
                "WHERE pr.is_active=1 AND p.status='active' AND p.stock_quantity>0 "
                "AND (? IS NULL OR p.product_id=?) ORDER BY p.product_id", (product_id, product_id),
            ).fetchall()
            products = [self.product(db, r) for r in rows]
        return {"products": products, "validity": "Active flag in supplied CSV; no start/end dates",
                "stacking": "Do not combine campaigns or add the 5% PIX discount"}

    def get_order_status(self, order_id: int, customer_id: int | None) -> dict:
        if customer_id is None:
            return {"error": "identity_required", "instruction": "Verify email and phone in sidebar"}
        with self.connect() as db:
            row = db.execute(
                "SELECT order_id,order_date,status,total_cents,payment_method,tracking_code,"
                "estimated_delivery,notes FROM orders WHERE order_id=? AND customer_id=?",
                (order_id, customer_id),
            ).fetchone()
            if not row:
                # Identical response for missing orders and orders belonging to other customers.
                return {"error": "order_not_found_for_verified_customer"}
            items = db.execute(
                "SELECT i.product_id,p.name,i.quantity FROM order_items i "
                "JOIN products p USING(product_id) WHERE i.order_id=?", (order_id,),
            ).fetchall()
        return {**dict(row), "total": brl(row["total_cents"]), "items": [dict(i) for i in items],
                "received_at": None, "sales_channel": None,
                "source": "CSV snapshot; estimated_delivery is not actual delivery or a new promise"}
