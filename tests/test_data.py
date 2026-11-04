import csv
import json
import shutil
import sqlite3

import pytest

from emporio.ingest import DataError, build_database, ensure_database, read_tables, sanitize
from emporio.text import brl, discounted, to_cents


def test_import_counts_foreign_keys_and_historical_totals(data_dir, tmp_path):
    destination = tmp_path / "db.sqlite3"
    report = build_database(data_dir, destination)
    assert report["rows"] == dict(
        categories=9, customers=50, products=65, orders=20, order_items=22, promotions=25
    )
    assert report["nulls"]["orders"]["tracking_code"] == 12
    assert [r["order_id"] for r in report["historical_total_mismatches"]] == [3, 20]
    with sqlite3.connect(destination) as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT total_cents FROM orders WHERE order_id=3").fetchone()[0] == 345000
        assert (
            db.execute("SELECT COUNT(*) FROM orders WHERE tracking_code IS NULL").fetchone()[0]
            == 12
        )


@pytest.mark.parametrize(
    "table,column,bad",
    [
        ("products", "category_id", "999"),
        ("products", "stock_quantity", "-1"),
        ("products", "price_brl", "NaN"),
        ("products", "price_brl", "10.001"),
        ("products", "specs", "not-json"),
        ("products", "status", "unknown"),
        ("products", "name", ""),
        ("products", "created_at", "yesterday"),
        ("order_items", "quantity", "0"),
        ("orders", "customer_id", "999"),
        ("orders", "estimated_delivery", "1990-01-01"),
        ("promotions", "is_active", "2"),
        ("promotions", "discount_percent", "100"),
    ],
)
def test_invalid_source_preserves_previous_database(data_dir, tmp_path, table, column, bad):
    source = tmp_path / "csvs"
    shutil.copytree(data_dir, source)
    database = tmp_path / "db.sqlite3"
    build_database(source, database)
    before = database.read_bytes()
    rows = read_tables(source)[table]
    rows[0][column] = bad
    with (source / f"{table}.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(DataError):
        build_database(source, database)
    assert database.read_bytes() == before


def test_duplicate_primary_key_rejected(data_dir, tmp_path):
    source = tmp_path / "csvs"
    shutil.copytree(data_dir, source)
    with (source / "products.csv").open("a", encoding="utf-8") as stream:
        with (data_dir / "products.csv").open(encoding="utf-8") as original:
            stream.write(original.readlines()[1])
    with pytest.raises(DataError):
        build_database(source, tmp_path / "db.sqlite3")


def test_ambiguous_file_names_rejected(data_dir, tmp_path):
    source = tmp_path / "csvs"
    shutil.copytree(data_dir, source)
    shutil.copy(source / "products.csv", source / "desafio_tecnico_ai_eng - products.csv")
    with pytest.raises(DataError):
        read_tables(source)


def test_unchanged_sources_do_not_rebuild(data_dir, tmp_path):
    path = tmp_path / "db.sqlite3"
    ensure_database(data_dir, path)
    timestamp = path.stat().st_mtime_ns
    ensure_database(data_dir, path)
    assert path.stat().st_mtime_ns == timestamp


def test_public_fixture_sanitization_is_reproducible(data_dir, tmp_path):
    destination = tmp_path / "public"
    sanitize(data_dir, destination)
    tables = read_tables(destination)
    assert all(r["email"].endswith("@example.invalid") for r in tables["customers"])
    assert all(r["phone"].startswith("00") for r in tables["customers"])
    assert all(r["name"].startswith("Cliente Demonstração") for r in tables["customers"])
    assert all(
        not r["tracking_code"] or r["tracking_code"].startswith("DEMO") for r in tables["orders"]
    )
    assert tables["products"] == read_tables(data_dir)["products"]
    build_database(destination, tmp_path / "sanitized.sqlite3")


def test_data_report_contains_no_customer_contacts(data_dir, tmp_path):
    report = json.dumps(build_database(data_dir, tmp_path / "db.sqlite3"))
    assert "@example.invalid" not in report
    assert "phone" in report  # Only the column name/counts are reported.


@pytest.mark.parametrize("value,expected", [("599.9", 59990), ("0", 0), ("2089.05", 208905)])
def test_exact_money(value, expected):
    assert to_cents(value) == expected
    assert discounted(219900, 5) == 208905
    assert brl(208905) == "R$ 2.089,05"
