from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

ToolStatus = Literal["success", "error", "denied", "mock"]
FinalStatus = Literal["PASS", "FAIL", "INCOMPLETE", "ERROR", "NO_REPAIR_NEEDED"]
Termination = Literal[
    "finish", "max_steps", "global_timeout", "protocol_errors", "no_progress",
    "model_error", "write_failed", "rollback_failed",
    "MODEL_TOOL_PROTOCOL_UNSUPPORTED",
    "no_repair_needed",
]
Permission = Literal["read_source", "read_tests", "execute", "write_temp", "write_target"]


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None
    function_index: int | None = None


@dataclass(frozen=True)
class AgentDecision:
    # Public, observable decision summary, never hidden chain-of-thought.
    thought: str = ""
    tool_call: ToolCall | None = None
    raw_response: Any = None
    kind: Literal["tool_call", "text", "protocol_error", "provider_error"] = "tool_call"
    error_code: str | None = None
    message: str = ""

    @property
    def decision_summary(self) -> str:
        return self.thought[:500]


@dataclass(frozen=True)
class ToolResult:
    status: ToolStatus
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    candidate_version: str = ""
    cached: bool = False


@dataclass(frozen=True)
class TrajectoryStep:
    step: int
    thought: str
    tool_call: ToolCall | None
    tool_result: ToolResult
    timestamp: str
    elapsed_seconds: float = 0.0
    raw_response: Any = None
    candidate_version: str = ""
    decision_summary: str = ""
    observation: dict[str, Any] = field(default_factory=dict)
    raw_result_ref: str = ""
    state_transition: dict[str, Any] = field(default_factory=dict)
    cached: bool = False


@dataclass
class AgentState:
    """Host-owned state. Models receive projections, never this mutable object."""

    candidate_code: str
    original_code: str
    project_root: Path
    source_path: Path
    test_path: Path | None = None
    test_code: str | None = None
    input_hashes: dict[str, str] = field(default_factory=dict)
    permissions: set[Permission] = field(default_factory=lambda: {
        "read_source", "read_tests", "execute", "write_temp",
    })
    applied_patches: list[str] = field(default_factory=list)
    snapshots: dict[str, bytes] = field(default_factory=dict)
    passed_checks: dict[str, str] = field(default_factory=dict)
    cache: dict[str, ToolResult] = field(default_factory=dict)
    call_counts: dict[str, int] = field(default_factory=dict)
    allow_test_rerun: bool = False
    risk_policy: Literal["reject", "mock", "requires_sandbox"] = "reject"
    rollback_result: str = "not_needed"
    execution_timeout_seconds: float = 10.0
    validation_config: dict[str, Any] = field(default_factory=dict)
    check_state_versions: dict[str, str] = field(default_factory=dict)
    last_execution_results: dict[str, ToolResult] = field(default_factory=dict)
    raw_results: dict[str, ToolResult] = field(default_factory=dict)
    deadline: float | None = None
    candidate_revision: int = 0
    candidate_history: list[dict[str, Any]] = field(default_factory=list)
    write_scope: set[str] = field(default_factory=set)
    config_hashes: dict[str, str] = field(default_factory=dict)
    regression_config: dict[str, Any] = field(default_factory=dict)
    initial_evidence: dict[str, Any] = field(default_factory=dict)
    check_results: dict[str, ToolResult] = field(default_factory=dict)
    check_result_contexts: dict[str, str] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return f"{self.candidate_revision}:{code_hash(self.candidate_code)}"

    @property
    def context_version(self) -> str:
        """Only state that can change a tool's result; not counters or cached evidence."""
        return code_hash(json.dumps({
            "validation": self.validation_config, "hashes": self.input_hashes,
            "test_code": self.test_code, "permissions": sorted(self.permissions),
            "risk_policy": self.risk_policy, "execution_timeout": self.execution_timeout_seconds,
            "write_scope": sorted(self.write_scope), "config_hashes": self.config_hashes,
            "regression": self.regression_config,
        }, sort_keys=True))

    @property
    def required_checks(self) -> set[str]:
        configured = self.validation_config.get("required_checks")
        if configured is not None:
            return set(configured)
        return {"validate_packages", "validate_apis", "execute"} | (
            {"run_pytest"} if self.test_code is not None else set()
        )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    permissions: tuple[Permission, ...] = ()
    cacheable: bool = False


class AgentModel(Protocol):
    model_name: str

    def decide(
        self, messages: list[dict[str, Any]], tools: list[ToolSpec], *, timeout_seconds: float,
    ) -> AgentDecision:
        """Choose exactly one action from the latest observations; no state mutation."""
        ...


ToolHandler = Callable[[AgentState, dict[str, Any], float], ToolResult]


class ToolDispatcher(Protocol):
    def register(self, spec: ToolSpec, handler: ToolHandler) -> None: ...

    def dispatch(self, state: AgentState, call: ToolCall, *, deadline: float) -> ToolResult: ...


@dataclass(frozen=True)
class AgentRunResult:
    final_status: FinalStatus
    termination_reason: Termination
    candidate_code: str
    candidate_version: str
    trajectory: list[TrajectoryStep]
    passed_checks: dict[str, str]
    input_hashes: dict[str, str]
    elapsed_seconds: float
    model_name: str
    applied: bool = False
    rollback_result: str = "not_needed"
    schema_version: int = 2
    persistence: dict[str, Any] = field(default_factory=dict)
    capability_probe: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    false_success: bool = False
    finish_verification: dict[str, Any] = field(default_factory=dict)
    candidate_revision: int = 0
    candidate_sha256: str = ""
    normalized_diff: str = ""
    config_hashes: dict[str, str] = field(default_factory=dict)
    regression_guard: dict[str, Any] = field(default_factory=dict)
    agent_invoked: bool = True
    initial_verification: dict[str, Any] = field(default_factory=dict)
    rejected_finish_count: int = 0
