from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2025-04-01-preview"
    request_timeout_seconds: float = 120.0
    planner_deployment: str = "gpt-5.4"
    specialist_deployment: str = "gpt-5.2-chat"
    synthesizer_deployment: str = "gpt-5.4"
    reviewer_deployment: str = "gpt-5.4"
    max_parallel: int = 3

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
            request_timeout_seconds=float(os.getenv("MULTI_AGENT_REQUEST_TIMEOUT_SECONDS", "120")),
            planner_deployment=os.getenv("MULTI_AGENT_PLANNER_DEPLOYMENT", "gpt-5.4"),
            specialist_deployment=os.getenv("MULTI_AGENT_SPECIALIST_DEPLOYMENT", "gpt-5.2-chat"),
            synthesizer_deployment=os.getenv("MULTI_AGENT_SYNTHESIZER_DEPLOYMENT", "gpt-5.4"),
            reviewer_deployment=os.getenv("MULTI_AGENT_REVIEWER_DEPLOYMENT", "gpt-5.4"),
            max_parallel=int(os.getenv("MULTI_AGENT_MAX_PARALLEL", "3")),
        )

    def validate_for_azure(self) -> None:
        missing: list[str] = []
        if not self.azure_openai_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.azure_openai_api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if missing:
            raise RuntimeError(
                "Azure orchestration mode requires environment variables: "
                + ", ".join(missing)
            )
