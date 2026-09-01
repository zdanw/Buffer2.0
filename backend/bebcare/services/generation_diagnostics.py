"""Build compact generation diagnostics from persisted run evidence."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from bebcare.models.generation_qds import GenerationDecisionEvent, GenerationReferenceSelection
from bebcare.models.generation_quality_finding import GenerationArtifactQualityFinding
from bebcare.models.generation_run import GenerationArtifact, GenerationRun
from bebcare.models.user import User
from bebcare.schemas.generation_diagnostics import (
    DiagnosticsGroup,
    DiagnosticsItem,
    DiagnosticsSummaryRow,
    GenerationDiagnostics,
)
from bebcare.services.quality_diversity_rollout import STRATEGY_FALLBACK, STRATEGY_OFF, STRATEGY_QDS

logger = logging.getLogger(__name__)

GROUP_KEYS = ("references", "intelligence", "protections", "quality", "diversity", "delivery")
SECRET_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "token",
        "secret",
        "password",
        "signed_url",
        "raw_response",
        "prompt",
        "image_bytes",
    }
)


def _item(code: str, status: str, **params: Any) -> DiagnosticsItem:
    clean = {k: v for k, v in params.items() if v is not None}
    return DiagnosticsItem(code=code, status=status, params=clean)  # type: ignore[arg-type]


def _group(status: str, items: list[DiagnosticsItem]) -> DiagnosticsGroup:
    return DiagnosticsGroup(status=status, items=items)  # type: ignore[arg-type]


def _worst(statuses: list[str]) -> str:
    order = [
        "blocked",
        "unavailable",
        "fallback",
        "warning",
        "skipped",
        "applied",
        "active",
        "passed",
        "off",
    ]
    for name in order:
        if name in statuses:
            return name
    return "off"


def _safe_dict(payload: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return None
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in SECRET_KEYS or "cdn_url" in lowered or "signed" in lowered:
                continue
            walked = _safe_dict(value, depth=depth + 1)
            if walked is not None:
                out[str(key)] = walked
        return out
    if isinstance(payload, list):
        return [_safe_dict(item, depth=depth + 1) for item in payload[:20]]
    if isinstance(payload, (str, int, float, bool)) or payload is None:
        if isinstance(payload, str) and len(payload) > 240:
            return payload[:240]
        return payload
    return None


def _event_types(events: list[GenerationDecisionEvent]) -> set[str]:
    return {e.event_type for e in events if e.event_type}


def _finding_codes(findings: list[GenerationArtifactQualityFinding]) -> list[str]:
    return [f.check_code for f in findings if f.check_code]


def log_material(
    *,
    code: str,
    stage: str,
    outcome: str,
    run_id: str | None,
    product_id: str | None = None,
    policy_version: str | None = None,
    artifact_index: int | None = None,
    extra: dict | None = None,
) -> None:
    payload = {
        "generation_run_id": run_id,
        "event": code,
        "stage": stage,
        "outcome": outcome,
        "policy_version": policy_version,
        "product_id": product_id,
        "artifact_index": artifact_index,
    }
    if extra:
        payload.update(_safe_dict(extra) or {})
    logger.info("generation_diagnostics", extra=payload)


def _diversity_from_run(
    run: GenerationRun,
    events: list[GenerationDecisionEvent],
    selection: GenerationReferenceSelection | None,
) -> tuple[str, list[DiagnosticsItem], str]:
    types = _event_types(events)
    requested = run.requested_selector_strategy or STRATEGY_OFF
    executed = run.executed_selector_strategy or STRATEGY_OFF
    items: list[DiagnosticsItem] = []
    if requested in (None, "", STRATEGY_OFF) and executed != STRATEGY_QDS:
        items.append(_item("qds_off", "off"))
        return "off", items, "qds_off"
    if "qds_skipped" in types or (executed != STRATEGY_QDS and requested != STRATEGY_QDS):
        if executed == STRATEGY_FALLBACK or run.fallback_reason:
            items.append(_item("selector_fallback", "fallback", reason=run.fallback_reason))
            return "fallback", items, "selector_fallback"
        items.append(_item("qds_skipped", "skipped"))
        return "skipped", items, "qds_skipped"
    if executed == STRATEGY_QDS or "qds_enabled" in types:
        items.append(_item("qds_active", "active"))
        if "weighted_selection" in types:
            pool = 0
            if selection and isinstance(selection.candidate_summary, dict):
                pool = len(selection.candidate_summary.get("eligible_ids") or [])
            items.append(_item("weighted_selection", "applied", pool=pool or None))
            if "cooldown_applied" in types or "diversity_penalty_applied" in types:
                items.append(_item("cooldown_applied", "applied"))
            return "applied", items, "weighted_selection"
        if "conservative_top_selection" in types:
            items.append(_item("conservative_top", "applied"))
            return "applied", items, "conservative_top"
        if "intentional_reference_reuse" in types:
            items.append(_item("intentional_reuse", "applied"))
            return "applied", items, "intentional_reuse"
        if "qds_rotation_disabled" in types:
            items.append(_item("qds_rotation_disabled", "skipped"))
            return "active", items, "qds_active"
        return "active", items, "qds_active"
    if executed == STRATEGY_FALLBACK or run.fallback_path:
        items.append(_item("selector_fallback", "fallback", reason=run.fallback_reason))
        return "fallback", items, "selector_fallback"
    items.append(_item("qds_off", "off"))
    return "off", items, "qds_off"


def _references_from_run(
    run: GenerationRun,
    events: list[GenerationDecisionEvent],
    selection: GenerationReferenceSelection | None,
) -> tuple[str, list[DiagnosticsItem], str, dict]:
    types = _event_types(events)
    items: list[DiagnosticsItem] = []
    params: dict[str, Any] = {}
    manifest = run.reference_manifest if isinstance(run.reference_manifest, dict) else {}
    raw_items = list(manifest.get("items") or [])
    product_n = sum(1 for row in raw_items if row.get("image_type") == "product")
    scene_n = sum(1 for row in raw_items if row.get("image_type") == "scene")
    params["product_count"] = product_n
    params["scene_count"] = scene_n
    coverage = selection.coverage_class if selection else (run.generation_plan or {}).get("reference_coverage") if isinstance(run.generation_plan, dict) else None
    if coverage:
        params["coverage"] = coverage
        items.append(_item("coverage_" + str(coverage), "applied" if coverage in ("limited", "insufficient") else "passed", coverage=coverage))
    if "preferred_reference_applied" in types:
        items.append(_item("preferred_reference", "applied"))
        return _worst([i.status for i in items] or ["applied"]), items, "preferred_reference", params
    if "explicit_pin_applied" in types:
        items.append(_item("explicit_pin", "applied"))
    if "support_reference_omitted" in types:
        items.append(_item("support_omitted", "skipped"))
    if "scene_reference_omitted" in types:
        items.append(_item("scene_omitted", "skipped"))
    if product_n:
        items.append(_item("references_selected", "applied", count=product_n, scene_count=scene_n))
    if "candidate_excluded" in types:
        items.append(_item("references_excluded", "warning"))
    if not items:
        items.append(_item("references_selected", "applied", count=product_n))
    message = "coverage_limited" if coverage in ("limited", "insufficient") else "references_selected"
    if "preferred_reference_applied" in types:
        message = "preferred_reference"
    return _worst([i.status for i in items]), items, message, params


def _intelligence_from_run(
    run: GenerationRun,
    events: list[GenerationDecisionEvent],
) -> tuple[str, list[DiagnosticsItem], str]:
    types = _event_types(events)
    plan = run.generation_plan if isinstance(run.generation_plan, dict) else {}
    trace = plan.get("selector_trace") if isinstance(plan.get("selector_trace"), dict) else {}
    availability = str(trace.get("intelligence_availability") or trace.get("intelligence_confidence_class") or "")
    items: list[DiagnosticsItem] = []
    if "intelligence_unavailable" in types or availability in ("missing", "failed", "unavailable"):
        items.append(_item("intelligence_unavailable", "unavailable"))
        return "unavailable", items, "intelligence_unavailable"
    used = bool(trace.get("usable_semantic_count"))
    if used:
        items.append(_item("intelligence_used", "applied"))
        cache = None
        intel = plan.get("asset_intelligence") if isinstance(plan.get("asset_intelligence"), dict) else None
        if isinstance(intel, dict) and intel.get("cache_hit") is True:
            items.append(_item("intelligence_cache_hit", "passed"))
            cache = "hit"
        elif isinstance(intel, dict) and intel.get("cache_hit") is False:
            items.append(_item("intelligence_cache_miss", "active"))
            cache = "miss"
        return "applied", items, "intelligence_used"
    if availability:
        items.append(_item("intelligence_unused", "skipped"))
        return "skipped", items, "intelligence_unused"
    if run.executed_pipeline_version and "grounded" in str(run.executed_pipeline_version):
        items.append(_item("deterministic_metadata", "active"))
        return "active", items, "deterministic_metadata"
    items.append(_item("intelligence_unused", "skipped"))
    return "skipped", items, "intelligence_unused"


def _protections_from_run(run: GenerationRun, events: list[GenerationDecisionEvent]) -> tuple[str, list[DiagnosticsItem], str]:
    types = _event_types(events)
    plan = run.generation_plan if isinstance(run.generation_plan, dict) else {}
    overlay = plan.get("fidelity") if isinstance(plan.get("fidelity"), dict) else {}
    logo = overlay.get("logo") if isinstance(overlay.get("logo"), dict) else {}
    items: list[DiagnosticsItem] = []
    mode = run.product_fidelity_prevention_mode
    extra = list(plan.get("extra_constraints") or []) + list(overlay.get("extra_constraints") or [])
    contradiction = plan.get("prompt_contradiction") if isinstance(plan.get("prompt_contradiction"), dict) else {}
    if not mode or mode == "off":
        items.append(_item("fidelity_off", "off"))
    else:
        items.append(_item("fidelity_active", "active"))
        if "unsupported_mount_removed" in types or any("unsupported_mount" in str(x) for x in extra):
            items.append(_item("unsupported_mount_removed", "applied"))
        if "stable_surface_fallback" in types or any("stable_surface" in str(x) for x in extra):
            items.append(_item("stable_surface_fallback", "applied"))
        if overlay.get("realistic_photo_sanitizer") or "realistic_photo_sanitizer" in types:
            items.append(_item("realistic_photo_sanitizer", "applied"))
        if not any(i.code in ("unsupported_mount_removed", "stable_surface_fallback") for i in items):
            items.append(_item("fidelity_no_rewrite", "passed"))
    if contradiction.get("applied") or "prompt_contradiction_resolved" in types:
        items.append(_item("prompt_contradiction_resolved", "applied"))
    elif contradiction.get("evaluated") or "prompt_contradiction_evaluated" in types:
        items.append(_item("prompt_contradiction_active", "active"))
    if logo.get("generated_branding_prohibited") or "generated_branding_prohibited" in types:
        items.append(_item("generated_branding_prohibited", "applied"))
    if logo.get("insert_wordmark_in_prompt") is False or "wordmark_withheld" in types:
        items.append(_item("wordmark_withheld", "applied"))
    applied = [i for i in items if i.status == "applied"]
    if applied:
        return "applied", items, applied[0].code
    if any(i.code == "fidelity_off" for i in items) and len(items) == 1:
        return "off", items, "fidelity_off"
    return "active", items, "fidelity_active"


def _quality_from_run(
    run: GenerationRun,
    findings: list[GenerationArtifactQualityFinding],
    artifacts: list[GenerationArtifact],
) -> tuple[str, list[DiagnosticsItem], str]:
    items: list[DiagnosticsItem] = []
    qmode = run.quality_protection_mode
    vmode = run.visual_fidelity_qa_mode
    if not qmode or qmode == "off":
        items.append(_item("quality_protection_off", "off"))
    codes = _finding_codes(findings)
    hard = [f for f in findings if f.severity == "hard_fail" and not f.passed]
    warns = [f for f in findings if f.severity == "warning" and not f.passed]
    visual_unavail = any(c in ("visual_qa_unavailable", "visual_qa_transport", "candidate_retrieval") for c in codes)
    if visual_unavail:
        items.append(_item("visual_qa_unavailable", "unavailable"))
        return "unavailable", items, "visual_qa_unavailable"
    elif vmode in (None, "", "off"):
        items.append(_item("visual_qa_off", "off"))
    elif any(f.qa_kind == "visual" for f in findings):
        items.append(_item("visual_qa_ran", "passed" if not hard else "blocked"))
    if hard:
        items.append(_item("hard_quality_fail", "blocked", reason=hard[0].check_code))
        return "blocked", items, "publish_blocked" if any("publish" in (f.stage or "") for f in hard) else "hard_quality_fail"
    if any(a.persistence_warning for a in artifacts):
        items.append(_item("cdn_persistence_warning", "warning"))
    if warns:
        items.append(_item("quality_warning", "warning"))
        return "warning", items, "quality_warning"
    if findings and not hard:
        items.append(_item("deterministic_qa_passed", "passed"))
        return "passed", items, "deterministic_qa_passed"
    if qmode and qmode != "off":
        items.append(_item("quality_checks_active", "active"))
        return "active", items, "quality_checks_active"
    return _worst([i.status for i in items] or ["off"]), items, items[0].code if items else "quality_protection_off"


def _delivery_from_run(
    run: GenerationRun,
    artifacts: list[GenerationArtifact],
    findings: list[GenerationArtifactQualityFinding],
) -> tuple[str, list[DiagnosticsItem], str]:
    items: list[DiagnosticsItem] = []
    selected = next((a for a in artifacts if a.selected), None)
    if selected is None and artifacts:
        selected = min(artifacts, key=lambda a: a.candidate_index)
    if selected and selected.candidate_index > 0:
        items.append(_item("sibling_selected", "applied", index=selected.candidate_index + 1))
    rejected = [a for a in artifacts if not a.selected and selected and a.candidate_index < selected.candidate_index]
    if rejected:
        items.append(_item("candidate_rejected", "blocked", index=rejected[0].candidate_index + 1))
    if any(a.persistence_warning for a in artifacts):
        items.append(_item("cdn_persistence_warning", "warning"))
    provider = run.model or run.provider_type or "provider"
    mode = run.image_provider_mode or "platform"
    items.append(
        _item(
            "provider_call",
            "applied" if run.status == "succeeded" else ("blocked" if run.status == "failed" else "active"),
            provider=provider,
            mode=mode,
            credits=run.credits_charged or 0,
            size=run.image_size,
            latency_ms=run.latency_ms,
        )
    )
    if run.status == "failed":
        items.append(_item("generation_failed", "blocked", category=run.error_category))
        return "blocked", items, "generation_failed"
    if any(i.code == "sibling_selected" for i in items):
        return "applied", items, "sibling_selected"
    if any(i.code == "cdn_persistence_warning" for i in items):
        return "warning", items, "cdn_persistence_warning"
    return "applied", items, "provider_call"


def _empty_groups() -> dict[str, DiagnosticsGroup]:
    return {key: _group("off", []) for key in GROUP_KEYS}


def build_planned_diagnostics(
    *,
    selection_payload: dict[str, Any],
    include_technical: bool = False,
) -> GenerationDiagnostics:
    """Planned checks from live selection. Does not claim execution of generation."""
    trace = selection_payload.get("selector_trace") if isinstance(selection_payload.get("selector_trace"), dict) else {}
    executed = selection_payload.get("executed_selector_strategy") or STRATEGY_OFF
    requested = selection_payload.get("requested_selector_strategy") or STRATEGY_OFF
    manifest = selection_payload.get("reference_manifest") or selection_payload.get("manifest") or {}
    items_m = list((manifest.get("items") if isinstance(manifest, dict) else []) or [])
    product_n = sum(1 for row in items_m if row.get("image_type") == "product")
    coverage = trace.get("coverage")
    groups = _empty_groups()
    ref_items = [_item("references_selected", "active", count=product_n)]
    if coverage:
        ref_items.append(_item("coverage_" + str(coverage), "active", coverage=coverage))
    groups["references"] = _group("active", ref_items)
    if executed == STRATEGY_QDS:
        reason = str(trace.get("selection_reason") or "")
        d_items = [_item("qds_active", "active")]
        msg = "qds_active"
        if reason == "conservative_top":
            d_items.append(_item("conservative_top", "applied"))
            msg = "conservative_top"
        elif reason == "weighted_eligible_pool":
            d_items.append(_item("weighted_selection", "applied"))
            msg = "weighted_selection"
        groups["diversity"] = _group("active", d_items)
        diversity_msg = msg
        diversity_status = "active"
    elif requested == STRATEGY_OFF or executed in (STRATEGY_OFF, None, ""):
        groups["diversity"] = _group("off", [_item("qds_off", "off")])
        diversity_msg = "qds_off"
        diversity_status = "off"
    else:
        groups["diversity"] = _group("skipped", [_item("qds_skipped", "skipped")])
        diversity_msg = "qds_skipped"
        diversity_status = "skipped"
    groups["intelligence"] = _group("active", [_item("intelligence_planned", "active")])
    groups["protections"] = _group(
        "active",
        [_item("fidelity_planned", "active"), _item("prompt_contradiction_planned", "active")],
    )
    groups["quality"] = _group("active", [_item("quality_checks_active", "active")])
    groups["delivery"] = _group("active", [_item("delivery_planned", "active")])
    summary = [
        DiagnosticsSummaryRow(key="references", status="active", message_key="references_selected", params={"count": product_n, "coverage": coverage}),
        DiagnosticsSummaryRow(key="intelligence", status="active", message_key="intelligence_planned"),
        DiagnosticsSummaryRow(key="protections", status="active", message_key="fidelity_planned"),
        DiagnosticsSummaryRow(key="quality", status="active", message_key="quality_checks_active"),
        DiagnosticsSummaryRow(key="diversity", status=diversity_status, message_key=diversity_msg),  # type: ignore[arg-type]
        DiagnosticsSummaryRow(key="delivery", status="active", message_key="delivery_planned"),
    ]
    technical = None
    if include_technical:
        technical = _safe_dict(
            {
                "selection_seed": selection_payload.get("selection_seed") or trace.get("selection_seed"),
                "executed_selector_strategy": executed,
                "requested_selector_strategy": requested,
                "event_codes": ["planned"],
            }
        )
    return GenerationDiagnostics(
        state="planned",
        has_history=True,
        summary=summary,
        groups=groups,
        technical=technical,
    )


def build_run_diagnostics(
    run: GenerationRun,
    *,
    events: list[GenerationDecisionEvent],
    selection: Optional[GenerationReferenceSelection],
    findings: list[GenerationArtifactQualityFinding],
    artifacts: list[GenerationArtifact],
    include_technical: bool,
) -> GenerationDiagnostics:
    has_history = bool(events or selection or run.generation_plan or run.executed_selector_strategy or findings)
    if run.status in ("pending", "running"):
        state = "running"
    elif run.status == "failed":
        state = "failed"
    else:
        state = "completed"
    if not has_history:
        return GenerationDiagnostics(
            state=state,  # type: ignore[arg-type]
            run_id=run.run_id,
            has_history=False,
            summary=[
                DiagnosticsSummaryRow(
                    key="history",
                    status="skipped",
                    message_key="no_detailed_history",
                )
            ],
            groups=_empty_groups(),
            technical={"run_id": run.run_id, "event_codes": []} if include_technical else None,
        )
    ref_status, ref_items, ref_msg, ref_params = _references_from_run(run, events, selection)
    intel_status, intel_items, intel_msg = _intelligence_from_run(run, events)
    prot_status, prot_items, prot_msg = _protections_from_run(run, events)
    qual_status, qual_items, qual_msg = _quality_from_run(run, findings, artifacts)
    div_status, div_items, div_msg = _diversity_from_run(run, events, selection)
    del_status, del_items, del_msg = _delivery_from_run(run, artifacts, findings)
    groups = {
        "references": _group(ref_status, ref_items),
        "intelligence": _group(intel_status, intel_items),
        "protections": _group(prot_status, prot_items),
        "quality": _group(qual_status, qual_items),
        "diversity": _group(div_status, div_items),
        "delivery": _group(del_status, del_items),
    }
    summary = [
        DiagnosticsSummaryRow(key="references", status=ref_status, message_key=ref_msg, params=ref_params),  # type: ignore[arg-type]
        DiagnosticsSummaryRow(key="intelligence", status=intel_status, message_key=intel_msg),  # type: ignore[arg-type]
        DiagnosticsSummaryRow(key="protections", status=prot_status, message_key=prot_msg),  # type: ignore[arg-type]
        DiagnosticsSummaryRow(key="quality", status=qual_status, message_key=qual_msg),  # type: ignore[arg-type]
        DiagnosticsSummaryRow(key="diversity", status=div_status, message_key=div_msg),  # type: ignore[arg-type]
        DiagnosticsSummaryRow(key="delivery", status=del_status, message_key=del_msg),  # type: ignore[arg-type]
    ]
    technical = None
    if include_technical:
        plan = run.generation_plan if isinstance(run.generation_plan, dict) else {}
        trace = plan.get("selector_trace") if isinstance(plan.get("selector_trace"), dict) else {}
        snap = (selection.candidate_summary or {}).get("history_snapshot") if selection and isinstance(selection.candidate_summary, dict) else None
        technical = _safe_dict(
            {
                "run_id": run.run_id,
                "artifact_ids": [a.artifact_id for a in artifacts],
                "selection_seed": run.selection_seed,
                "history_snapshot": snap,
                "policy_versions": {
                    "selector": trace.get("selector_policy_version"),
                    "quality": run.quality_policy_version,
                    "visual": run.visual_fidelity_policy_version,
                    "contradiction": (plan.get("prompt_contradiction") or {}).get("policy_version")
                    if isinstance(plan.get("prompt_contradiction"), dict)
                    else None,
                },
                "event_codes": sorted(_event_types(events)),
                "effective_weights": (selection.candidate_summary or {}).get("effective_weights") if selection and isinstance(selection.candidate_summary, dict) else None,
                "executed_selector_strategy": run.executed_selector_strategy,
                "requested_selector_strategy": run.requested_selector_strategy,
                "fallback_reason": run.fallback_reason,
            }
        )
    return GenerationDiagnostics(
        state=state,  # type: ignore[arg-type]
        run_id=run.run_id,
        has_history=True,
        summary=summary,
        groups=groups,
        technical=technical,
    )


def load_run_bundle(db: Session, run: GenerationRun) -> tuple[
    list[GenerationDecisionEvent],
    Optional[GenerationReferenceSelection],
    list[GenerationArtifactQualityFinding],
    list[GenerationArtifact],
]:
    selection = (
        db.query(GenerationReferenceSelection)
        .filter(
            GenerationReferenceSelection.generation_run_id == run.run_id,
            GenerationReferenceSelection.owner_user_id == run.owner_user_id,
        )
        .first()
    )
    events = (
        db.query(GenerationDecisionEvent)
        .filter(
            GenerationDecisionEvent.generation_run_id == run.run_id,
            GenerationDecisionEvent.owner_user_id == run.owner_user_id,
        )
        .order_by(GenerationDecisionEvent.sequence_number.asc())
        .all()
    )
    findings = (
        db.query(GenerationArtifactQualityFinding)
        .filter(
            GenerationArtifactQualityFinding.generation_run_id == run.run_id,
            GenerationArtifactQualityFinding.owner_user_id == run.owner_user_id,
        )
        .all()
    )
    artifacts = list(run.artifacts or [])
    return events, selection, findings, artifacts


def diagnostics_for_run(
    db: Session,
    run: GenerationRun,
    *,
    viewer: User | None = None,
    include_technical: bool | None = None,
) -> GenerationDiagnostics:
    events, selection, findings, artifacts = load_run_bundle(db, run)
    technical = include_technical if include_technical is not None else bool(viewer and viewer.is_admin)
    return build_run_diagnostics(
        run,
        events=events,
        selection=selection,
        findings=findings,
        artifacts=artifacts,
        include_technical=technical,
    )


def diagnostics_for_task(db: Session, task_id: str, *, viewer: User) -> Optional[GenerationDiagnostics]:
    run = (
        db.query(GenerationRun)
        .filter(
            GenerationRun.generate_task_id == task_id,
            GenerationRun.owner_user_id == viewer.user_id,
        )
        .order_by(GenerationRun.created_at.desc())
        .first()
    )
    if not run:
        return None
    return diagnostics_for_run(db, run, viewer=viewer)
