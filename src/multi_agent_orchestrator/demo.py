from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings
from .orchestrator import Orchestrator


def write_run_artifacts(out_dir: Path, run) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "execution-plan.json").write_text(run.plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (out_dir / "review.json").write_text(run.review.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (out_dir / "run-summary.json").write_text(
        (
            "{\n"
            f'  "request_id": "{run.request_id}",\n'
            f'  "fallback_used": {"true" if run.fallback_used else "false"},\n'
            f'  "steps": {len(run.plan.steps)},\n'
            f'  "artifacts": {len(run.artifacts)},\n'
            f'  "total_tokens": {run.total_tokens},\n'
            f'  "recommendation": "{run.review.release_recommendation}",\n'
            f'  "coverage_score": {run.review.coverage_score}\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    (out_dir / "execution-events.json").write_text(
        "[\n"
        + ",\n".join(event.model_dump_json(indent=2) for event in run.events)
        + "\n]\n",
        encoding="utf-8",
    )
    (out_dir / "decision-memo.md").write_text(run.final_memo_markdown.rstrip() + "\n", encoding="utf-8")
    for index, artifact in enumerate(run.artifacts, start=1):
        file_name = f"{index:02d}-{artifact.step_id}.md"
        body = [
            f"# {artifact.title}",
            "",
            f"Agent: `{artifact.agent_name}`",
            "",
        ]
        if artifact.summary_bullets:
            body.append("## Summary Bullets")
            body.append("")
            body.extend(f"- {bullet}" for bullet in artifact.summary_bullets)
            body.append("")
        body.append("## Notes")
        body.append("")
        body.append(artifact.content_markdown.rstrip())
        body.append("")
        (out_dir / file_name).write_text("\n".join(body), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the multi-agent technical review demo.")
    parser.add_argument("--brief-file", required=True, help="Markdown brief to analyze.")
    parser.add_argument("--goal", required=True, help="Review goal for the orchestration.")
    parser.add_argument("--out-dir", required=True, help="Directory for generated artifacts.")
    args = parser.parse_args()

    brief_path = Path(args.brief_file)
    out_dir = Path(args.out_dir)
    brief_markdown = brief_path.read_text(encoding="utf-8")
    orchestrator = Orchestrator(settings=Settings.from_env())
    run = orchestrator.run(
        goal=args.goal,
        brief_title=brief_path.stem.replace("-", " "),
        brief_markdown=brief_markdown,
    )
    write_run_artifacts(out_dir, run)


if __name__ == "__main__":
    main()
