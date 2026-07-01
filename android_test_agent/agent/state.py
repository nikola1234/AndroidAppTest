from __future__ import annotations

from typing import Any, Literal, TypedDict


class ExecutionResult(TypedDict, total=False):
    status: Literal["not_run", "dry_run", "passed", "failed"]
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    generated_test_path: str


class ValidationResult(TypedDict, total=False):
    passed: bool
    reason: str
    failure_type: str | None
    exception_class: str
    error_signature: str
    stack_summary: list[str]
    failing_action: str
    failing_target: str
    fingerprint: str
    suggestions: list[str]


class AgentState(TypedDict, total=False):
    raw_case: str
    analyzed_requirements: dict[str, Any]
    plan: dict[str, Any]
    intent_dsl: dict[str, Any]
    resolved_dsl: dict[str, Any]
    dsl: dict[str, Any]
    generated_files: dict[str, str]
    execution_result: ExecutionResult
    validation_result: ValidationResult
    element_resolution: dict[str, Any]
    human_review: dict[str, Any]
    retry_count: int
    errors: list[str]
    artifacts: dict[str, str]
    metadata: dict[str, Any]
