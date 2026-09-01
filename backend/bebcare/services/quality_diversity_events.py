"""Durable QDS / generation decision events. Persistence failure must not crash generation."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from bebcare.models.generation_qds import GenerationDecisionEvent, GenerationReferenceSelection
from bebcare.models.generation_run import GenerationRun
from bebcare.services.ownership import stamp_owner
from bebcare.services.quality_diversity_policy import SELECTOR_POLICY_VERSION
from bebcare.services.quality_diversity_rollout import (
    STRATEGY_FALLBACK,
    STRATEGY_GROUNDED,
    STRATEGY_OFF,
    STRATEGY_QDS,
    quality_diversity_enabled,
    quality_diversity_selector_mode,
)

logger = logging.getLogger(__name__)

REDACT_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "token",
        "secret",
        "password",
        "cdn_url",
        "signed_url",
        "raw_response",
        "prompt",
        "image_bytes",
    }
)
EVENT_LIMIT = 20
DETAIL_CAP = 4000


def _safe_details(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    def _walk(value: Any, depth: int = 0) -> Any:
        if depth > 4:
            return None
        if isinstance(value, dict):
            out = {}
            for key, item in list(value.items())[:40]:
                low = str(key).lower()
                if any(part in low for part in REDACT_KEYS):
                    continue
                cleaned = _walk(item, depth + 1)
                if cleaned is not None:
                    out[key] = cleaned
            return out
        if isinstance(value, list):
            return [_walk(item, depth + 1) for item in value[:40]]
        if isinstance(value, float):
            return round(value, 4)
        if isinstance(value, (str, int, bool)) or value is None:
            text = value if not isinstance(value, str) else value[:500]
            return text
        return str(value)[:200]

    return _walk(payload)


def _owner(run: GenerationRun):
    return type("Owner", (), {"user_id": run.owner_user_id})()


def resolve_executed_strategy(
    *,
    source: str,
    task_mode: str | None,
    grounded: bool,
    qds_ran: bool,
    fallback_reason: str | None,
) -> str:
    requested = quality_diversity_selector_mode()
    if requested == "off" or not grounded:
        return STRATEGY_OFF if requested == "off" else STRATEGY_GROUNDED
    if fallback_reason:
        return STRATEGY_FALLBACK
    if qds_ran and quality_diversity_enabled(source=source, task_mode=task_mode, grounded=True):
        return STRATEGY_QDS
    return STRATEGY_GROUNDED


def persist_selection_observability(
    db: Session,
    run: GenerationRun,
    *,
    source: str,
    task_mode: str | None = None,
    grounded: bool = False,
    qds_ran: bool = False,
    fallback_reason: str | None = None,
    seed: str | None = None,
    trace: dict | None = None,
    manifest: dict | None = None,
    scene_id: str | None = None,
) -> None:
    """One selection row + a short event sequence. Never raises to the caller."""
    try:
        existing = (
            db.query(GenerationReferenceSelection)
            .filter(GenerationReferenceSelection.generation_run_id == run.run_id)
            .first()
        )
        if existing:
            return
        nested = db.begin_nested()
        requested = quality_diversity_selector_mode()
        executed = resolve_executed_strategy(
            source=source,
            task_mode=task_mode,
            grounded=grounded,
            qds_ran=qds_ran,
            fallback_reason=fallback_reason,
        )
        if executed == STRATEGY_FALLBACK:
            qds_ran = False
        run.requested_selector_strategy = requested
        run.executed_selector_strategy = executed
        if seed:
            run.selection_seed = seed
        trace = trace if isinstance(trace, dict) else {}
        primary = None
        if isinstance(manifest, dict):
            items = manifest.get("items") or []
            if items:
                primary = items[0].get("image_id")
        primary = primary or (trace.get("selected_ids") or [None])[0]
        row = GenerationReferenceSelection(
            generation_run_id=run.run_id,
            selector_version=str(trace.get("selector_policy_version") or SELECTOR_POLICY_VERSION),
            seed=seed,
            strategy=executed,
            requested_strategy=requested,
            executed_strategy=executed,
            risk_profile=trace.get("risk_band"),
            coverage_class=trace.get("coverage"),
            selected_primary_image_id=primary,
            selected_scene_image_id=scene_id,
            candidate_summary=_safe_details(
                {
                    "eligible_ids": (trace.get("eligible_candidate_ids") or [])[:20],
                    "exclusions": (trace.get("exclusion_reasons") or [])[:20],
                    "selection_reason": trace.get("selection_reason"),
                    "weighted_rotation_enabled": trace.get("weighted_rotation_enabled"),
                    "effective_weights": trace.get("effective_weights"),
                    "history_snapshot": {
                        "run_ids": ((trace.get("history_snapshot") or {}).get("run_ids") or [])[:12],
                        "cutoff_run_id": (trace.get("history_snapshot") or {}).get("cutoff_run_id"),
                        "entry_count": (trace.get("history_snapshot") or {}).get("entry_count"),
                        "entries": ((trace.get("history_snapshot") or {}).get("entries") or [])[:12],
                    },
                }
            ),
            selected_manifest=_safe_details(manifest) if manifest else None,
            fingerprint=_safe_details(trace.get("fingerprint") or {}),
        )
        stamp_owner(row, _owner(run))
        db.add(row)
        events = _events_from_trace(
            requested=requested,
            executed=executed,
            qds_ran=qds_ran,
            fallback_reason=fallback_reason,
            seed=seed,
            trace=trace,
        )
        for index, event in enumerate(events[:EVENT_LIMIT]):
            rec = GenerationDecisionEvent(
                generation_run_id=run.run_id,
                sequence_number=index,
                event_type=event["event_type"],
                stage=event.get("stage") or "select",
                outcome=event.get("outcome"),
                severity=event.get("severity") or "info",
                policy_name="quality_diversity_selector",
                policy_version=SELECTOR_POLICY_VERSION,
                summary=(event.get("summary") or "")[:500],
                details=_safe_details(event.get("details") or {}),
            )
            stamp_owner(rec, _owner(run))
            db.add(rec)
        nested.commit()
        logger.info(
            "generation_diagnostics",
            extra={
                "generation_run_id": run.run_id,
                "event": "selector_observability_persisted",
                "stage": "select",
                "outcome": "ok",
                "policy_version": SELECTOR_POLICY_VERSION,
                "product_id": getattr(run, "product_id", None),
            },
        )
    except Exception:
        logger.warning("qds_observability_persist_failed", extra={"run_id": getattr(run, "run_id", None)})


def _events_from_trace(
    *,
    requested: str,
    executed: str,
    qds_ran: bool,
    fallback_reason: str | None,
    seed: str | None,
    trace: dict,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if requested == "off" or not qds_ran:
        events.append(
            {
                "event_type": "qds_skipped",
                "summary": "QDS did not execute",
                "details": {"requested": requested, "executed": executed, "reason": fallback_reason},
            }
        )
    else:
        events.append(
            {
                "event_type": "qds_enabled",
                "summary": "QDS executed",
                "details": {"requested": requested, "executed": executed, "seed": seed},
            }
        )
    reason = str(trace.get("selection_reason") or "")
    if reason == "preferred_authority":
        events.append({"event_type": "preferred_reference_applied", "summary": "Preferred primary retained"})
    if reason == "explicit_pin":
        events.append({"event_type": "explicit_pin_applied", "summary": "Explicit pin retained"})
    if reason == "conservative_top":
        events.append({"event_type": "conservative_top_selection", "summary": "Conservative top selection"})
    if reason == "weighted_eligible_pool":
        events.append(
            {
                "event_type": "weighted_selection",
                "summary": "Seeded weighted selection",
                "details": {"seed": seed, "weights": trace.get("effective_weights")},
            }
        )
        logger.info("qds_weighted_selection", extra={"seed": seed})
    if reason == "intentional_reuse" or trace.get("intentional_reuse"):
        events.append({"event_type": "intentional_reference_reuse", "summary": "Only one safe reference reused"})
    exclusions = trace.get("exclusion_reasons") or []
    if exclusions:
        events.append(
            {
                "event_type": "candidate_excluded",
                "stage": "select",
                "summary": f"{len(exclusions)} candidates excluded",
                "details": {"excluded": exclusions[:20]},
            }
        )
    eligible = trace.get("eligible_candidate_ids") or []
    if eligible:
        events.append(
            {
                "event_type": "eligible_pool_created",
                "summary": f"{len(eligible)} eligible primary candidates",
                "details": {"eligible_ids": eligible[:20]},
            }
        )
    if trace.get("diversity_penalties"):
        events.append(
            {
                "event_type": "diversity_penalty_applied",
                "summary": "History cooldown applied",
                "details": {"penalties": trace.get("diversity_penalties")},
            }
        )
        events.append({"event_type": "cooldown_applied", "summary": "Recent-use cooldown factored"})
    if trace.get("selected_ids"):
        events.append(
            {
                "event_type": "primary_reference_selected",
                "summary": "Primary reference selected",
                "details": {"image_id": (trace.get("selected_ids") or [None])[0], "seed": seed},
            }
        )
    supports = (trace.get("selected_ids") or [])[1:]
    if supports:
        events.append(
            {
                "event_type": "supporting_reference_selected",
                "summary": "Supporting references selected",
                "details": {"image_ids": supports[:8]},
            }
        )
    if trace.get("coverage"):
        events.append(
            {
                "event_type": "reference_coverage_classified",
                "summary": f"Coverage {trace.get('coverage')}",
                "details": {"coverage": trace.get("coverage"), "reasons": trace.get("risk_reasons")},
            }
        )
    if trace.get("shot_family"):
        events.append(
            {
                "event_type": "shot_family_selected",
                "summary": str(trace.get("shot_family")),
                "details": {"shot_family": trace.get("shot_family")},
            }
        )
    if qds_ran and trace.get("weighted_rotation_enabled") is False:
        events.append(
            {
                "event_type": "qds_rotation_disabled",
                "summary": "Weighted rotation disabled",
                "details": {"reason": trace.get("weighted_rotation_disabled_reason")},
            }
        )
    usable = int(trace.get("usable_semantic_count") or 0)
    if qds_ran and usable == 0:
        events.append(
            {
                "event_type": "intelligence_unavailable",
                "severity": "warning",
                "summary": "Asset intelligence unavailable",
            }
        )
    selected_ids = list(trace.get("selected_ids") or [])
    if qds_ran and len(selected_ids) <= 1:
        events.append({"event_type": "support_reference_omitted", "summary": "No supporting reference selected"})
    if fallback_reason:
        events.append(
            {
                "event_type": "selector_fallback",
                "severity": "warning",
                "summary": "Selector fallback",
                "details": {"reason": fallback_reason, "executed": executed},
            }
        )
        logger.info("qds_selector_fallback", extra={"reason": fallback_reason})
    return events


def attach_from_product_info(
    db: Session,
    run: GenerationRun,
    product_info: dict | None,
    *,
    source: str,
    task_mode: str | None = None,
) -> None:
    info = product_info or {}
    provenance = info.get("generation_provenance") or {}
    executed = provenance.get("executed_selector_strategy") or run.executed_selector_strategy
    persist_selection_observability(
        db,
        run,
        source=source,
        task_mode=task_mode,
        grounded=bool(provenance.get("grounded_phase1b_enabled") or info.get("grounded")),
        qds_ran=executed == STRATEGY_QDS,
        fallback_reason=provenance.get("fallback_reason"),
        seed=provenance.get("selection_seed") or run.selection_seed,
        trace=provenance.get("selector_trace"),
        manifest=provenance.get("reference_manifest") or info.get("reference_manifest"),
    )


def compact_admin_timeline(
    run: GenerationRun,
    events: list[GenerationDecisionEvent],
    selection: Optional[GenerationReferenceSelection],
) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "selector_strategy": run.executed_selector_strategy or STRATEGY_OFF,
        "requested_strategy": run.requested_selector_strategy,
        "chosen_references": (selection.selected_manifest if selection else None),
        "exclusions_summary": (selection.candidate_summary or {}).get("exclusions") if selection else None,
        "seed": run.selection_seed,
        "coverage": selection.coverage_class if selection else None,
        "diversity_action": next(
            (
                e.event_type
                for e in events
                if e.event_type
                in (
                    "weighted_selection",
                    "conservative_top_selection",
                    "intentional_reference_reuse",
                )
            ),
            None,
        ),
        "events": [
            {
                "sequence": e.sequence_number,
                "event_type": e.event_type,
                "summary": e.summary,
                "stage": e.stage,
                "outcome": e.outcome,
            }
            for e in events
        ],
        "legacy": selection is None and not events,
    }


def expanded_admin_timeline(
    run: GenerationRun,
    events: list[GenerationDecisionEvent],
    selection: Optional[GenerationReferenceSelection],
) -> dict[str, Any]:
    compact = compact_admin_timeline(run, events, selection)
    compact["expanded"] = True
    compact["selection"] = None
    if selection:
        compact["selection"] = {
            "selector_version": selection.selector_version,
            "risk_profile": selection.risk_profile,
            "fingerprint": selection.fingerprint,
            "candidate_summary": selection.candidate_summary,
        }
    compact["event_details"] = [
        {
            "sequence": e.sequence_number,
            "event_type": e.event_type,
            "policy_version": e.policy_version,
            "details": e.details,
        }
        for e in events
    ]
    return compact
