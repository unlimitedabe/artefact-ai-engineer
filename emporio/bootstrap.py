"""Shared construction for UI, CLI and transcript generation."""

from emporio.agent import Agent
from emporio.config import Settings
from emporio.demo import DemoProvider
from emporio.ingest import ensure_database
from emporio.policies import PolicyIndex
from emporio.provider import OpenAIProvider
from emporio.store import Store
from emporio.tools import Tools


def resources(settings: Settings) -> tuple[Store, PolicyIndex]:
    ensure_database(settings.data_dir, settings.database_path)
    return Store(settings.database_path), PolicyIndex(settings.policy_pdf)


def create_agent(
    settings: Settings, store: Store, policies: PolicyIndex, customer_id: int | None = None
) -> Agent:
    provider = DemoProvider() if settings.mode == "demo" else OpenAIProvider(settings)
    return Agent(
        provider,
        Tools(store, policies, customer_id),
        settings.max_tool_rounds,
        settings.max_history_turns,
    )
