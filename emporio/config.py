"""Environment-backed application settings."""

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    api_key: str = Field(default="", repr=False)
    model: str = "gpt-4.1-mini"
    data_dir: Path = Path("fixtures/public")
    policy_pdf: Path = Path("data/políticas_da_loja.pdf")
    database_path: Path = Path("runtime/store.sqlite3")
    max_tool_rounds: int = Field(default=5, ge=1, le=10)
    max_history_turns: int = Field(default=8, ge=1, le=20)
    mode: Literal["openai", "demo"] = "openai"

    @classmethod
    def from_env(cls) -> "Settings":
        import os

        load_dotenv()
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            data_dir=Path(os.getenv("DATA_DIR", "fixtures/public")),
            policy_pdf=Path(os.getenv("POLICY_PDF", "data/políticas_da_loja.pdf")),
            database_path=Path(os.getenv("DATABASE_PATH", "runtime/store.sqlite3")),
            max_tool_rounds=os.getenv("MAX_TOOL_ROUNDS", "5"),
            max_history_turns=os.getenv("MAX_HISTORY_TURNS", "8"),
            mode=os.getenv("AGENT_MODE", "openai"),
        )
