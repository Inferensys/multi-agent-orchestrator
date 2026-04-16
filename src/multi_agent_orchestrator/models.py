from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AgentSpec(BaseModel):
    name: str
    title: str
    instruction: str


class PlanStep(BaseModel):
    id: str
    title: str
    objective: str
    assigned_agent: str
    deliverable: str


class ExecutionPlan(BaseModel):
    goal: str
    final_deliverable: str
    steps: list[PlanStep] = Field(default_factory=list)


class SpecialistDraft(BaseModel):
    title: str
    summary_bullets: list[str] = Field(default_factory=list)
    content_markdown: str


class SpecialistArtifact(BaseModel):
    step_id: str
    agent_name: str
    title: str
    summary_bullets: list[str] = Field(default_factory=list)
    content_markdown: str


class ReviewFinding(BaseModel):
    severity: Literal["high", "medium", "low"]
    title: str
    detail: str


class ReviewReport(BaseModel):
    coverage_score: int = Field(ge=0, le=100)
    release_recommendation: Literal["ready", "needs-work", "blocked"]
    findings: list[ReviewFinding] = Field(default_factory=list)
    missing_threads: list[str] = Field(default_factory=list)


class CompletionRecord(BaseModel):
    role: str
    deployment: str
    output_text: str
    finish_reason: str | None = None
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ExecutionEvent(BaseModel):
    event: str
    step_id: str | None = None
    agent_name: str | None = None
    status: Literal["started", "completed", "failed", "fallback"] | None = None
    timestamp: datetime
    notes: str | None = None


class OrchestrationRun(BaseModel):
    request_id: str
    brief_title: str
    goal: str
    fallback_used: bool = False
    started_at: datetime
    completed_at: datetime
    plan: ExecutionPlan
    artifacts: list[SpecialistArtifact] = Field(default_factory=list)
    final_memo_markdown: str
    review: ReviewReport
    model_calls: list[CompletionRecord] = Field(default_factory=list)
    events: list[ExecutionEvent] = Field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(record.total_tokens for record in self.model_calls)
