"""Concrete multi-agent review orchestration with Azure-backed specialists."""

from .config import Settings
from .models import (
    AgentSpec,
    CompletionRecord,
    ExecutionEvent,
    ExecutionPlan,
    OrchestrationRun,
    PlanStep,
    ReviewFinding,
    ReviewReport,
    SpecialistArtifact,
)
from .orchestrator import Orchestrator
from .prompts import default_agent_specs

__version__ = "0.2.0"

__all__ = [
    "AgentSpec",
    "CompletionRecord",
    "ExecutionEvent",
    "ExecutionPlan",
    "Orchestrator",
    "OrchestrationRun",
    "PlanStep",
    "ReviewFinding",
    "ReviewReport",
    "Settings",
    "SpecialistArtifact",
    "default_agent_specs",
]
