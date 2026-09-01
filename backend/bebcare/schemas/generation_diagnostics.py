"""Compact generation diagnostics. Codes only; UI localizes."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

DiagState = Literal["planned", "running", "completed", "failed"]
DiagStatus = Literal[
    "active",
    "applied",
    "passed",
    "warning",
    "blocked",
    "skipped",
    "unavailable",
    "fallback",
    "off",
]


class DiagnosticsItem(BaseModel):
    code: str
    status: DiagStatus
    params: dict[str, Any] = Field(default_factory=dict)


class DiagnosticsGroup(BaseModel):
    status: DiagStatus
    items: list[DiagnosticsItem] = Field(default_factory=list)


class DiagnosticsSummaryRow(BaseModel):
    key: str
    status: DiagStatus
    message_key: str
    params: dict[str, Any] = Field(default_factory=dict)


class GenerationDiagnostics(BaseModel):
    state: DiagState
    run_id: Optional[str] = None
    has_history: bool = True
    summary: list[DiagnosticsSummaryRow] = Field(default_factory=list)
    groups: dict[str, DiagnosticsGroup] = Field(default_factory=dict)
    technical: Optional[dict[str, Any]] = None
