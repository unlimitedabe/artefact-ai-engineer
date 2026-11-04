from datetime import date
from pathlib import Path

import pytest

from emporio.ingest import build_database
from emporio.policies import PolicyIndex
from emporio.store import Store
from emporio.tools import Tools

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def data_dir():
    return ROOT / "fixtures/public"


@pytest.fixture(scope="session")
def database(tmp_path_factory, data_dir):
    path = tmp_path_factory.mktemp("db") / "store.sqlite3"
    build_database(data_dir, path)
    return path


@pytest.fixture
def store(database):
    return Store(database)


@pytest.fixture(scope="session")
def policies():
    return PolicyIndex(ROOT / "data/políticas_da_loja.pdf")


@pytest.fixture
def tools(store, policies):
    return Tools(store, policies, today=date(2026, 3, 22))
