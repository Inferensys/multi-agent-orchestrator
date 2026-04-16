from __future__ import annotations

from multi_agent_orchestrator.config import Settings
from multi_agent_orchestrator.models import (
    ChatMessage,
    CompletionRecord,
    ExecutionPlan,
    ReviewFinding,
    ReviewReport,
    SpecialistDraft,
)
from multi_agent_orchestrator.orchestrator import Orchestrator


class FakeLLM:
    def __init__(self, *, invalid_plan: bool = False) -> None:
        self.invalid_plan = invalid_plan
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, *, role, deployment, messages, max_output_tokens, response_model):
        self.calls.append((role, deployment))
        if response_model is ExecutionPlan:
            if self.invalid_plan:
                return (
                    ExecutionPlan(
                        goal="invalid",
                        final_deliverable="memo",
                        steps=[
                            {
                                "id": "bad-step",
                                "title": "Bad",
                                "objective": "Bad",
                                "assigned_agent": "unknown",
                                "deliverable": "Bad",
                            }
                        ],
                    ),
                    self._record(role, deployment, "{}"),
                )
            return (
                ExecutionPlan(
                    goal="review launch",
                    final_deliverable="decision memo",
                    steps=[
                        {
                            "id": "architecture-fit",
                            "title": "Architecture fit",
                            "objective": "Review architecture boundaries.",
                            "assigned_agent": "architecture",
                            "deliverable": "Architecture position.",
                        },
                        {
                            "id": "security-scope",
                            "title": "Security scope",
                            "objective": "Review tenant and data risks.",
                            "assigned_agent": "security",
                            "deliverable": "Security controls.",
                        },
                    ],
                ),
                self._record(role, deployment, "{}"),
            )
        if response_model is SpecialistDraft:
            agent_name = role.split(":", 1)[1]
            return (
                SpecialistDraft(
                    title=f"{agent_name.title()} Notes",
                    summary_bullets=[f"{agent_name} summary"],
                    content_markdown=f"## {agent_name.title()}\n\nConcrete recommendation.",
                ),
                self._record(role, deployment, "{}"),
            )
        if response_model is ReviewReport:
            return (
                ReviewReport(
                    coverage_score=84,
                    release_recommendation="needs-work",
                    findings=[
                        ReviewFinding(
                            severity="medium",
                            title="Guardrail gap",
                            detail="The memo needs stronger canary metrics.",
                        )
                    ],
                    missing_threads=["rollback drill evidence"],
                ),
                self._record(role, deployment, "{}"),
            )
        raise AssertionError(f"Unexpected response model: {response_model}")

    def complete_text(self, *, role, deployment, messages, max_output_tokens):
        self.calls.append((role, deployment))
        assert all(isinstance(message, ChatMessage) for message in messages)
        return self._record(
            role,
            deployment,
            "# Decision\n\nPilot is acceptable with a narrow blast radius.\n",
        )

    @staticmethod
    def _record(role: str, deployment: str, output_text: str) -> CompletionRecord:
        return CompletionRecord(
            role=role,
            deployment=deployment,
            output_text=output_text,
            finish_reason="stop",
            latency_ms=12,
            prompt_tokens=100,
            completion_tokens=80,
            total_tokens=180,
        )


def build_orchestrator(fake_llm: FakeLLM) -> Orchestrator:
    settings = Settings(
        planner_deployment="planner-model",
        specialist_deployment="specialist-model",
        synthesizer_deployment="synth-model",
        reviewer_deployment="review-model",
        max_parallel=2,
    )
    return Orchestrator(settings=settings, llm=fake_llm)


def test_orchestrator_runs_plan_and_preserves_step_order() -> None:
    orchestrator = build_orchestrator(FakeLLM())
    run = orchestrator.run(
        goal="review launch",
        brief_title="brief",
        brief_markdown="System brief.",
    )

    assert run.fallback_used is False
    assert [artifact.step_id for artifact in run.artifacts] == ["architecture-fit", "security-scope"]
    assert run.review.release_recommendation == "needs-work"
    assert run.total_tokens == 180 * 5


def test_orchestrator_uses_fallback_plan_when_planner_is_invalid() -> None:
    orchestrator = build_orchestrator(FakeLLM(invalid_plan=True))
    run = orchestrator.run(
        goal="review launch",
        brief_title="brief",
        brief_markdown="System brief.",
    )

    assert run.fallback_used is True
    assert len(run.plan.steps) == 4
    assert run.events[0].event == "planner_fallback"
