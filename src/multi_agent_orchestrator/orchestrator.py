from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from .client import AzureChatClient
from .config import Settings
from .models import (
    AgentSpec,
    ChatMessage,
    CompletionRecord,
    ExecutionEvent,
    ExecutionPlan,
    OrchestrationRun,
    PlanStep,
    ReviewReport,
    SpecialistArtifact,
    SpecialistDraft,
)
from .prompts import (
    default_agent_specs,
    planner_messages,
    review_messages,
    specialist_messages,
    synthesizer_messages,
)


class Orchestrator:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        llm: AzureChatClient | None = None,
        agent_specs: list[AgentSpec] | None = None,
    ) -> None:
        self._settings = settings or Settings.from_env()
        self._llm = llm or AzureChatClient(self._settings)
        self._agent_specs = agent_specs or default_agent_specs()
        self._agent_index = {agent.name: agent for agent in self._agent_specs}

    def run(
        self,
        *,
        goal: str,
        brief_title: str,
        brief_markdown: str,
    ) -> OrchestrationRun:
        return asyncio.run(
            self.run_async(
                goal=goal,
                brief_title=brief_title,
                brief_markdown=brief_markdown,
            )
        )

    async def run_async(
        self,
        *,
        goal: str,
        brief_title: str,
        brief_markdown: str,
    ) -> OrchestrationRun:
        started_at = datetime.now(timezone.utc)
        request_id = str(uuid.uuid4())
        model_calls: list[CompletionRecord] = []
        events: list[ExecutionEvent] = []

        plan, fallback_used, planner_record = await self._build_plan(
            goal=goal,
            brief_markdown=brief_markdown,
            events=events,
        )
        model_calls.append(planner_record)

        artifacts = await self._run_specialists(
            goal=goal,
            brief_title=brief_title,
            brief_markdown=brief_markdown,
            plan=plan,
            model_calls=model_calls,
            events=events,
        )

        final_memo_markdown, synthesis_record = await self._synthesize(
            goal=goal,
            brief_title=brief_title,
            brief_markdown=brief_markdown,
            plan=plan,
            artifacts=artifacts,
            events=events,
        )
        model_calls.append(synthesis_record)

        review, review_record = await self._review(
            goal=goal,
            brief_markdown=brief_markdown,
            final_memo_markdown=final_memo_markdown,
            events=events,
        )
        model_calls.append(review_record)

        completed_at = datetime.now(timezone.utc)
        return OrchestrationRun(
            request_id=request_id,
            brief_title=brief_title,
            goal=goal,
            fallback_used=fallback_used,
            started_at=started_at,
            completed_at=completed_at,
            plan=plan,
            artifacts=artifacts,
            final_memo_markdown=final_memo_markdown,
            review=review,
            model_calls=model_calls,
            events=events,
        )

    async def _build_plan(
        self,
        *,
        goal: str,
        brief_markdown: str,
        events: list[ExecutionEvent],
    ) -> tuple[ExecutionPlan, bool, CompletionRecord]:
        system, user = planner_messages(
            goal=goal,
            brief_markdown=brief_markdown,
            agent_specs=self._agent_specs,
        )
        try:
            plan, record = await asyncio.to_thread(
                self._llm.complete_json,
                role="planner",
                deployment=self._settings.planner_deployment,
                messages=[
                    ChatMessage(role="system", content=system),
                    ChatMessage(role="user", content=user),
                ],
                max_output_tokens=1600,
                response_model=ExecutionPlan,
            )
            self._validate_plan(plan)
            return plan, False, record
        except Exception as exc:
            fallback_plan = self._fallback_plan(goal)
            events.append(
                ExecutionEvent(
                    event="planner_fallback",
                    status="fallback",
                    timestamp=datetime.now(timezone.utc),
                    notes=str(exc),
                )
            )
            fallback_record = CompletionRecord(
                role="planner",
                deployment=self._settings.planner_deployment,
                output_text=fallback_plan.model_dump_json(indent=2),
                finish_reason="fallback",
                latency_ms=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            )
            return fallback_plan, True, fallback_record

    async def _run_specialists(
        self,
        *,
        goal: str,
        brief_title: str,
        brief_markdown: str,
        plan: ExecutionPlan,
        model_calls: list[CompletionRecord],
        events: list[ExecutionEvent],
    ) -> list[SpecialistArtifact]:
        semaphore = asyncio.Semaphore(self._settings.max_parallel)

        async def run_step(step: PlanStep) -> SpecialistArtifact:
            agent = self._agent_index[step.assigned_agent]
            started_at = datetime.now(timezone.utc)
            events.append(
                ExecutionEvent(
                    event="specialist_step",
                    step_id=step.id,
                    agent_name=agent.name,
                    status="started",
                    timestamp=started_at,
                    notes=step.title,
                )
            )
            try:
                async with semaphore:
                    system, user = specialist_messages(
                        goal=goal,
                        brief_title=brief_title,
                        brief_markdown=brief_markdown,
                        step_id=step.id,
                        step_title=step.title,
                        step_objective=step.objective,
                        deliverable=step.deliverable,
                        agent=agent,
                    )
                    draft, record = await asyncio.to_thread(
                        self._llm.complete_json,
                        role=f"specialist:{agent.name}",
                        deployment=self._settings.specialist_deployment,
                        messages=[
                            ChatMessage(role="system", content=system),
                            ChatMessage(role="user", content=user),
                        ],
                        max_output_tokens=1800,
                        response_model=SpecialistDraft,
                    )
                    model_calls.append(record)
                    artifact = SpecialistArtifact(
                        step_id=step.id,
                        agent_name=agent.name,
                        title=draft.title,
                        summary_bullets=draft.summary_bullets,
                        content_markdown=draft.content_markdown,
                    )
                    events.append(
                        ExecutionEvent(
                            event="specialist_step",
                            step_id=step.id,
                            agent_name=agent.name,
                            status="completed",
                            timestamp=datetime.now(timezone.utc),
                            notes=artifact.title,
                        )
                    )
                    return artifact
            except Exception as exc:
                events.append(
                    ExecutionEvent(
                        event="specialist_step",
                        step_id=step.id,
                        agent_name=agent.name,
                        status="failed",
                        timestamp=datetime.now(timezone.utc),
                        notes=str(exc),
                    )
                )
                raise

        completed = await asyncio.gather(*(run_step(step) for step in plan.steps))
        artifact_index = {artifact.step_id: artifact for artifact in completed}
        return [artifact_index[step.id] for step in plan.steps]

    async def _synthesize(
        self,
        *,
        goal: str,
        brief_title: str,
        brief_markdown: str,
        plan: ExecutionPlan,
        artifacts: list[SpecialistArtifact],
        events: list[ExecutionEvent],
    ) -> tuple[str, CompletionRecord]:
        events.append(
            ExecutionEvent(
                event="synthesis",
                status="started",
                timestamp=datetime.now(timezone.utc),
                notes="final decision memo",
            )
        )
        system, user = synthesizer_messages(
            goal=goal,
            brief_title=brief_title,
            brief_markdown=brief_markdown,
            plan=plan,
            artifacts=[
                f"## {artifact.title}\nAgent: {artifact.agent_name}\n\n{artifact.content_markdown}"
                for artifact in artifacts
            ],
        )
        record = await asyncio.to_thread(
            self._llm.complete_text,
            role="synthesizer",
            deployment=self._settings.synthesizer_deployment,
            messages=[
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=user),
            ],
            max_output_tokens=2200,
        )
        events.append(
            ExecutionEvent(
                event="synthesis",
                status="completed",
                timestamp=datetime.now(timezone.utc),
                notes="final decision memo",
            )
        )
        return record.output_text, record

    async def _review(
        self,
        *,
        goal: str,
        brief_markdown: str,
        final_memo_markdown: str,
        events: list[ExecutionEvent],
    ) -> tuple[ReviewReport, CompletionRecord]:
        events.append(
            ExecutionEvent(
                event="review",
                status="started",
                timestamp=datetime.now(timezone.utc),
                notes="principal review",
            )
        )
        system, user = review_messages(
            goal=goal,
            brief_markdown=brief_markdown,
            final_memo_markdown=final_memo_markdown,
        )
        report, record = await asyncio.to_thread(
            self._llm.complete_json,
            role="reviewer",
            deployment=self._settings.reviewer_deployment,
            messages=[
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=user),
            ],
            max_output_tokens=1200,
            response_model=ReviewReport,
        )
        events.append(
            ExecutionEvent(
                event="review",
                status="completed",
                timestamp=datetime.now(timezone.utc),
                notes=report.release_recommendation,
            )
        )
        return report, record

    def _validate_plan(self, plan: ExecutionPlan) -> None:
        if not plan.steps:
            raise ValueError("Planner returned zero steps.")
        if len(plan.steps) > 4:
            raise ValueError("Planner returned too many steps.")
        seen_ids: set[str] = set()
        for step in plan.steps:
            if step.id in seen_ids:
                raise ValueError(f"Duplicate step id: {step.id}")
            if step.assigned_agent not in self._agent_index:
                raise ValueError(f"Unknown agent: {step.assigned_agent}")
            seen_ids.add(step.id)

    def _fallback_plan(self, goal: str) -> ExecutionPlan:
        return ExecutionPlan(
            goal=goal,
            final_deliverable="Decision memo with recommendation, launch blockers, and rollout guardrails.",
            steps=[
                PlanStep(
                    id="architecture-fit",
                    title="Architecture fit",
                    objective="Check where deterministic routing, policy, and fallback logic must stay outside the model.",
                    assigned_agent="architecture",
                    deliverable="A clear architecture position with required boundaries.",
                ),
                PlanStep(
                    id="security-scope",
                    title="Security scope",
                    objective="Review sensitive data handling, trust boundaries, and tenant isolation risks.",
                    assigned_agent="security",
                    deliverable="A list of controls and launch blockers.",
                ),
                PlanStep(
                    id="production-readiness",
                    title="Production readiness",
                    objective="Review latency budgets, rollback, tracing, and service ownership gaps.",
                    assigned_agent="operations",
                    deliverable="A rollout and observability view.",
                ),
                PlanStep(
                    id="eval-coverage",
                    title="Eval coverage",
                    objective="Check whether acceptance criteria and failure modes are measurable before pilot release.",
                    assigned_agent="evals",
                    deliverable="An eval and guardrail assessment.",
                ),
            ],
        )
