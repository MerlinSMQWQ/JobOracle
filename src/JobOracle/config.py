from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH)


@dataclass(slots=True)
class EmploymentConfig:
    api_key: str = (
        os.getenv("EMPLOYMENT_API_KEY")
        or os.getenv("REPORT_ENGINE_API_KEY")
        or os.getenv("QUERY_ENGINE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    )
    base_url: str = (
        os.getenv("EMPLOYMENT_BASE_URL")
        or os.getenv("REPORT_ENGINE_BASE_URL")
        or os.getenv("QUERY_ENGINE_BASE_URL")
        or "https://api.openai.com/v1"
    )
    model_name: str = (
        os.getenv("EMPLOYMENT_MODEL_NAME")
        or os.getenv("REPORT_ENGINE_MODEL_NAME")
        or os.getenv("QUERY_ENGINE_MODEL_NAME")
        or "gpt-4o-mini"
    )
    timeout_seconds: int = int(os.getenv("EMPLOYMENT_TIMEOUT_SECONDS", "120"))
    report_dir: Path = Path(os.getenv("EMPLOYMENT_REPORT_DIR", PROJECT_ROOT / "reports"))
    search_api_key: str = os.getenv("EMPLOYMENT_SEARCH_API_KEY") or os.getenv("TAVILY_API_KEY") or ""
    search_provider: str = os.getenv("EMPLOYMENT_SEARCH_PROVIDER", "tavily").lower()
    search_timeout_seconds: int = int(os.getenv("EMPLOYMENT_SEARCH_TIMEOUT_SECONDS", "30"))
    max_search_results: int = int(os.getenv("EMPLOYMENT_MAX_SEARCH_RESULTS", "8"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.api_key and self.base_url and self.model_name)

    @property
    def search_enabled(self) -> bool:
        return bool(self.search_api_key and self.search_provider)


def get_config() -> EmploymentConfig:
    return EmploymentConfig()
