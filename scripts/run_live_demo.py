from __future__ import annotations

from pathlib import Path

from multi_agent_orchestrator.demo import write_run_artifacts
from multi_agent_orchestrator.orchestrator import Orchestrator


GOAL = (
    "Decide whether the platform team should approve a pilot rollout of the AI release reviewer "
    "described in the brief, and identify the controls required before it touches production change management."
)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    brief_path = root / "demo" / "input" / "release-review-brief.md"
    out_dir = root / "demo" / "output"
    orchestrator = Orchestrator()
    run = orchestrator.run(
        goal=GOAL,
        brief_title="release review brief",
        brief_markdown=brief_path.read_text(encoding="utf-8"),
    )
    write_run_artifacts(out_dir, run)


if __name__ == "__main__":
    main()
