"""Validate the six CSV tables and atomically build a local SQLite snapshot."""

import csv
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from emporio.text import normalize, to_cents

SCHEMAS = {
    "categories": ["category_id", "name", "description"],
    "customers": ["customer_id", "name", "phone", "email", "city"],
    "products": [
        "product_id", "price_brl", "name", "category_id", "description", "stock_quantity",
        "status", "specs", "created_at",
    ],
    "orders": [
        "order_id", "customer_id", "order_date", "status", "total_brl", "payment_method",
        "tracking_code", "estimated_delivery", "notes",
    ],
    "order_items": ["order_id", "quantity", "product_id"],
    "promotions": ["promotion_id", "product_id", "discount_percent", "description", "is_active"],
}

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE categories (category_id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT);
CREATE TABLE customers (
 customer_id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE, city TEXT NOT NULL);
CREATE TABLE products (
 product_id INTEGER PRIMARY KEY, price_cents INTEGER NOT NULL CHECK(price_cents>=0),
 name TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories,
 description TEXT NOT NULL, stock_quantity INTEGER NOT NULL CHECK(stock_quantity>=0),
 status TEXT NOT NULL CHECK(status IN ('active','discontinued','coming_soon')),
 specs TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE orders (
 order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers,
 order_date TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('pending','confirmed','shipped','delivered','cancelled')),
 total_cents INTEGER NOT NULL CHECK(total_cents>=0), payment_method TEXT NOT NULL,
 tracking_code TEXT, estimated_delivery TEXT, notes TEXT);
CREATE TABLE order_items (
 order_id INTEGER NOT NULL REFERENCES orders, quantity INTEGER NOT NULL CHECK(quantity>0),
 product_id INTEGER NOT NULL REFERENCES products, PRIMARY KEY(order_id,product_id));
CREATE TABLE promotions (
 promotion_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products,
 discount_percent INTEGER NOT NULL CHECK(discount_percent BETWEEN 1 AND 99),
 description TEXT NOT NULL, is_active INTEGER NOT NULL CHECK(is_active IN (0,1)));
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_promotions_product ON promotions(product_id,is_active);
"""


class DataError(ValueError):
    """A source file failed validation; no partial database is published."""


def source_files(directory: Path) -> dict[str, Path]:
    """Accept canonical filenames or the exact challenge export names, never ambiguous inputs."""
    result = {}
    for table in SCHEMAS:
        matches = [p for p in [directory / f"{table}.csv",
                              directory / f"desafio_tecnico_ai_eng - {table}.csv"] if p.exists()]
        if len(matches) != 1:
            raise DataError(f"Expected exactly one CSV for {table} in {directory}")
        result[table] = matches[0]
    return result


def fingerprint(files: dict[str, Path]) -> str:
    digest = hashlib.sha256(b"emporio-schema-v1")
    for table, path in sorted(files.items()):
        digest.update(table.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def read_tables(directory: Path) -> dict[str, list[dict[str, str]]]:
    tables = {}
    for table, path in source_files(directory).items():
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != SCHEMAS[table]:
                raise DataError(f"Unexpected columns in {path.name}; expected {SCHEMAS[table]}")
            rows = list(reader)
        if not rows:
            raise DataError(f"Empty table: {table}")
        for number, row in enumerate(rows, 2):
            if None in row or any(v is None for v in row.values()):
                raise DataError(f"Malformed row {number} in {table}")
            optional = {"tracking_code", "estimated_delivery", "notes"}
            if any(not value.strip() for key, value in row.items() if key not in optional):
                raise DataError(f"Missing required value in {table} at row {number}")
        tables[table] = rows
    return tables


def integer(value: str, minimum: int = 1) -> int:
    if not re.fullmatch(r"\d+", value) or int(value) < minimum:
        raise DataError("Invalid nonnegative integer field")
    return int(value)


def build_database(directory: Path, destination: Path) -> dict:
    """Each call validates and rebuilds. Failed builds leave the previous snapshot intact."""
    tables = read_tables(directory)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="store-", suffix=".sqlite3", dir=destination.parent)
    os.close(fd)
    db = sqlite3.connect(temporary)
    try:
        db.executescript(DDL)
        with db:
            for r in tables["categories"]:
                db.execute("INSERT INTO categories VALUES (?,?,?)",
                           (integer(r["category_id"]), r["name"], r["description"]))
            for r in tables["customers"]:
                email = r["email"].strip().casefold()
                phone = re.sub(r"\D", "", r["phone"])
                if "@" not in email or len(phone) not in (10, 11, 12, 13):
                    raise DataError("Invalid customer contact format")
                db.execute("INSERT INTO customers VALUES (?,?,?,?,?)",
                           (integer(r["customer_id"]), r["name"], phone, email, r["city"]))
            for r in tables["products"]:
                if not isinstance(json.loads(r["specs"]), dict):
                    raise DataError("Product specs must be a JSON object")
                date.fromisoformat(r["created_at"])
                db.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)", (
                    integer(r["product_id"]), to_cents(r["price_brl"]), r["name"],
                    integer(r["category_id"]), r["description"], integer(r["stock_quantity"], 0),
                    r["status"], r["specs"], r["created_at"],
                ))
            for r in tables["orders"]:
                date.fromisoformat(r["order_date"])
                if r["estimated_delivery"]:
                    if date.fromisoformat(r["estimated_delivery"]) < date.fromisoformat(r["order_date"]):
                        raise DataError("Estimated delivery precedes order date")
                if r["payment_method"] not in {
                    "pix", "debit", "boleto", "credit_3x", "credit_6x", "credit_12x",
                }:
                    raise DataError("Unknown payment method")
                db.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", (
                    integer(r["order_id"]), integer(r["customer_id"]), r["order_date"], r["status"],
                    to_cents(r["total_brl"]), r["payment_method"], r["tracking_code"] or None,
                    r["estimated_delivery"] or None, r["notes"] or None,
                ))
            for r in tables["order_items"]:
                db.execute("INSERT INTO order_items VALUES (?,?,?)",
                           (integer(r["order_id"]), integer(r["quantity"]), integer(r["product_id"])))
            for r in tables["promotions"]:
                db.execute("INSERT INTO promotions VALUES (?,?,?,?,?)", (
                    integer(r["promotion_id"]), integer(r["product_id"]),
                    integer(r["discount_percent"]), r["description"], integer(r["is_active"], 0),
                ))
            missing_items = db.execute(
                "SELECT order_id FROM orders WHERE order_id NOT IN (SELECT order_id FROM order_items)"
            ).fetchall()
            if missing_items:
                raise DataError("An order has no line items")
            mismatches = db.execute("""
                SELECT o.order_id, o.total_cents, SUM(i.quantity*p.price_cents)
                FROM orders o JOIN order_items i USING(order_id)
                JOIN products p USING(product_id) GROUP BY o.order_id
                HAVING o.total_cents != SUM(i.quantity*p.price_cents)
            """).fetchall()
            report = {
                "encoding": "utf-8-sig",
                "rows": {table: len(rows) for table, rows in tables.items()},
                "nulls": {table: {col: sum(not r[col] for r in rows) for col in SCHEMAS[table]}
                          for table, rows in tables.items()},
                "historical_total_mismatches": [
                    {"order_id": a, "recorded_cents": b, "current_catalog_cents": c}
                    for a, b, c in mismatches
                ],
                "warnings": [
                    "Order totals are historical authoritative values, not current catalogue sums.",
                    "Promotions have an active flag but no validity dates.",
                    "Orders have estimated delivery but no actual receipt date or sales channel.",
                ],
            }
            db.execute("INSERT INTO metadata VALUES ('fingerprint',?)",
                       (fingerprint(source_files(directory)),))
            db.execute("INSERT INTO metadata VALUES ('report',?)", (json.dumps(report),))
        db.close()
        os.replace(temporary, destination)
        return report
    except (ValueError, sqlite3.Error, ArithmeticError) as exc:
        raise DataError(f"Dataset validation failed ({type(exc).__name__}); check source CSVs") from exc
    finally:
        db.close()
        Path(temporary).unlink(missing_ok=True)


def ensure_database(directory: Path, destination: Path) -> None:
    current = fingerprint(source_files(directory))
    if destination.exists():
        try:
            with sqlite3.connect(f"{destination.resolve().as_uri()}?mode=ro", uri=True) as db:
                row = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
                if row and row[0] == current:
                    return
        except sqlite3.Error:
            pass
    build_database(directory, destination)


def sanitize(source: Path, destination: Path) -> dict:
    """Publish synthetic contacts and tracking, preserving relational business facts."""
    if source.resolve() == destination.resolve():
        raise DataError("Sanitization destination must differ from original data")
    tables = read_tables(source)
    destination.mkdir(parents=True, exist_ok=True)
    for table, rows in tables.items():
        for r in rows:
            if table == "customers":
                customer_id = int(r["customer_id"])
                r.update(name=f"Cliente Demonstração {customer_id:02d}",
                         phone=f"0000000{customer_id:04d}",
                         email=f"customer{customer_id:02d}@example.invalid", city="Cidade Demonstração")
            elif table == "orders":
                if r["tracking_code"]:
                    r["tracking_code"] = f"DEMO{int(r['order_id']):09d}"
                # Notes are free text: do not risk copying identifiers into public fixtures.
                r["notes"] = "Cancelamento registrado; consulte a equipe." if r["notes"] else ""
        with (destination / f"{table}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SCHEMAS[table])
            writer.writeheader()
            writer.writerows(rows)
    return {table: len(rows) for table, rows in tables.items()}
