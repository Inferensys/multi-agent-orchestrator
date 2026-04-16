from __future__ import annotations

import json

from .models import AgentSpec, ExecutionPlan, ReviewReport, SpecialistDraft


def default_agent_specs() -> list[AgentSpec]:
    return [
        AgentSpec(
            name="architecture",
            title="Architecture Review",
            instruction=(
                "You are the staff architect. Focus on service boundaries, state ownership, "
                "fallback paths, and operational simplicity. Call out hidden coupling and "
                "where deterministic code should remain outside the model."
            ),
        ),
        AgentSpec(
            name="security",
            title="Security Review",
            instruction=(
                "You are the security reviewer. Focus on data classes, tenant isolation, "
                "authz boundaries, secrets handling, logging risk, prompt injection surfaces, "
                "and vendor dependency exposure."
            ),
        ),
        AgentSpec(
            name="operations",
            title="Operations Review",
            instruction=(
                "You are the production readiness reviewer. Focus on latency budgets, retries, "
                "backpressure, observability, rollout safety, incident response, and handoff "
                "from experiment to service ownership."
            ),
        ),
        AgentSpec(
            name="evals",
            title="Evals Review",
            instruction=(
                "You are the evaluation lead. Focus on acceptance criteria, failure taxonomy, "
                "offline and online eval coverage, rollout guardrails, and what evidence is "
                "missing to justify launch."
            ),
        ),
    ]


def planner_schema_hint() -> str:
    return json.dumps(ExecutionPlan.model_json_schema(), indent=2)


def specialist_schema_hint() -> str:
    return json.dumps(SpecialistDraft.model_json_schema(), indent=2)


def review_schema_hint() -> str:
    return json.dumps(ReviewReport.model_json_schema(), indent=2)


def planner_messages(*, goal: str, brief_markdown: str, agent_specs: list[AgentSpec]) -> tuple[str, str]:
    available_agents = "\n".join(
        f"- {agent.name}: {agent.title}. {agent.instruction}" for agent in agent_specs
    )
    system = (
        "Build a compact, execution-ready multi-agent plan. "
        "Return JSON only. Use 3 to 4 steps. Each step must use one available agent exactly as named. "
        "Avoid duplicated scopes. Prefer architecture, security, operations, and evals if the brief supports them."
    )
    user = (
        f"Goal:\n{goal}\n\n"
        f"Available specialists:\n{available_agents}\n\n"
        "Return an execution plan with a strong final deliverable. "
        "Schema:\n"
        f"{planner_schema_hint()}\n\n"
        f"Brief:\n{brief_markdown}"
    )
    return system, user


def specialist_messages(
    *,
    goal: str,
    brief_title: str,
    brief_markdown: str,
    step_id: str,
    step_title: str,
    step_objective: str,
    deliverable: str,
    agent: AgentSpec,
) -> tuple[str, str]:
    system = (
        f"{agent.instruction} "
        "Return JSON only. Be direct. Prefer specific recommendations over generic caveats. "
        "If evidence is missing, say what must be measured or instrumented."
    )
    user = (
        f"Goal:\n{goal}\n\n"
        f"Brief title:\n{brief_title}\n\n"
        f"Assigned step:\n- id: {step_id}\n- title: {step_title}\n- objective: {step_objective}\n- deliverable: {deliverable}\n\n"
        "Return the specialist output using this schema:\n"
        f"{specialist_schema_hint()}\n\n"
        f"Brief:\n{brief_markdown}"
    )
    return system, user


def synthesizer_messages(
    *,
    goal: str,
    brief_title: str,
    brief_markdown: str,
    plan: ExecutionPlan,
    artifacts: list[str],
) -> tuple[str, str]:
    system = (
        "Write the final decision memo for a technical review board. "
        "Do not mention that multiple agents were used. "
        "Use markdown. Be concise, decisive, and specific."
    )
    user = (
        f"Goal:\n{goal}\n\n"
        f"Brief title:\n{brief_title}\n\n"
        "Write a decision memo with these sections:\n"
        "- Decision\n"
        "- Why This Design Holds\n"
        "- Risks That Block A Wider Rollout\n"
        "- Instrumentation And Guardrails\n"
        "- Next 2 Engineering Moves\n\n"
        f"Plan:\n{plan.model_dump_json(indent=2)}\n\n"
        f"Brief:\n{brief_markdown}\n\n"
        "Specialist artifacts:\n"
        + "\n\n".join(artifacts)
    )
    return system, user


def review_messages(
    *,
    goal: str,
    brief_markdown: str,
    final_memo_markdown: str,
) -> tuple[str, str]:
    system = (
        "Review the decision memo like a principal engineer. "
        "Score coverage, decide if the release is ready, and list the remaining gaps. "
        "Return JSON only."
    )
    user = (
        f"Goal:\n{goal}\n\n"
        "Return the review using this schema:\n"
        f"{review_schema_hint()}\n\n"
        f"Brief:\n{brief_markdown}\n\n"
        f"Decision memo:\n{final_memo_markdown}"
    )
    return system, user
