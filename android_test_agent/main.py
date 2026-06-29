from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from android_test_agent.agent import AndroidTestAgent, AndroidTestConfig
from android_test_agent.agent.nodes.human_review import HumanReviewRejected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Android Appium tests with an AI agent.")
    parser.add_argument("--case", help="Raw test case text.")
    parser.add_argument("--case-file", help="Path to a YAML/text test case file.")
    parser.add_argument("--execute", action="store_true", help="Run generated pytest code.")
    parser.add_argument("--thread-id", help="Checkpoint thread id used to group this run.")
    parser.add_argument("--resume-from-checkpoint", help="Path to a JSON checkpoint to resume from.")
    parser.add_argument("--review-intent-dsl", action="store_true", help="Pause for approval after intent DSL generation.")
    parser.add_argument("--llm-codegen", action="store_true", help="Use LLM-based pytest code generation.")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    args = parse_args()

    config = AndroidTestConfig.from_env(Path.cwd())
    if args.execute:
        config.execute_generated_tests = True
    if args.review_intent_dsl:
        config.review_intent_dsl = True
    if args.llm_codegen:
        config.llm_codegen_enabled = True

    agent = AndroidTestAgent(config)
    try:
        if args.resume_from_checkpoint:
            state = agent.resume_from_checkpoint(args.resume_from_checkpoint, thread_id=args.thread_id)
        else:
            raw_case = args.case or _read_case_file(args.case_file) or _default_case()
            state = agent.run(raw_case, thread_id=args.thread_id)
        print(json.dumps(_summary(state), ensure_ascii=False, indent=2))
    except HumanReviewRejected as exc:
        print(json.dumps({"status": "human_review_required", "message": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(2) from exc
    finally:
        agent.close()


def _read_case_file(case_file: str | None) -> str | None:
    if not case_file:
        return None
    return Path(case_file).read_text(encoding="utf-8")


def _default_case() -> str:
    return Path("tests/test_cases_example.yaml").read_text(encoding="utf-8")


def _summary(state: dict) -> dict:
    return {
        "name": state.get("dsl", {}).get("name"),
        "generated_files": state.get("generated_files"),
        "execution_result": state.get("execution_result"),
        "validation_result": state.get("validation_result"),
        "retry_count": state.get("retry_count", 0),
        "checkpoint_thread_id": state.get("metadata", {}).get("checkpoint_thread_id"),
        "last_checkpoint": state.get("metadata", {}).get("last_checkpoint"),
        "resumed_from_checkpoint": state.get("metadata", {}).get("resumed_from_checkpoint"),
        "human_review": state.get("human_review"),
        "codegen_mode": state.get("metadata", {}).get("codegen_mode"),
    }


if __name__ == "__main__":
    main()
