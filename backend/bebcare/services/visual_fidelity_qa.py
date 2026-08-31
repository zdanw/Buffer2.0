"""Persist visual fidelity findings onto Phase 3A quality-finding rows."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from bebcare.models.generation_quality_finding import GenerationArtifactQualityFinding
from bebcare.models.generation_run import GenerationArtifact, GenerationRun
from bebcare.schemas.visual_fidelity import (
    LOGO_CHECK_CODES,
    VisualFidelityAssessment,
    normalize_check,
    publication_decision_from_checks,
    user_message_for_visual,
    warning_code_for_visual,
)
from bebcare.services.asset_intelligence_policy import AnalysisFailure
from bebcare.services.product_fidelity_prevention import model_facing_image_label
from bebcare.services.product_fidelity_rollout import (
    PREVENTION_POLICY_VERSION,
    VISUAL_POLICY_VERSION,
    visual_fidelity_enabled,
    visual_qa_entitled,
)
from bebcare.services.quality_protection import (
    SEV_HARD,
    SEV_INFO,
    SEV_WARNING,
    STAGE_POST,
    candidate_is_eligible,
    record_finding,
)
from bebcare.services.visual_fidelity_adapter import (
    assess_visual_fidelity,
    visual_qa_model_version,
)

logger = logging.getLogger(__name__)
QA_KIND_VISUAL = "visual_fidelity"
QA_KIND_DETERMINISTIC = "deterministic"
SECRET_KEY_FRAGMENTS = ("api_key", "apikey", "secret", "password", "token", "authorization", "private_key")


def canonical_digest(value: Any) -> str:
    def _strip(obj: Any) -> Any:
        if isinstance(obj, dict):
            cleaned = {}
            for key, item in sorted(obj.items(), key=lambda kv: str(kv[0])):
                low = str(key).lower()
                if any(frag in low for frag in SECRET_KEY_FRAGMENTS):
                    continue
                cleaned[str(key)] = _strip(item)
            return cleaned
        if isinstance(obj, list):
            return [_strip(item) for item in obj]
        if isinstance(obj, tuple):
            return [_strip(item) for item in obj]
        return obj

    payload = json.dumps(_strip(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ref_entry(item: dict | None) -> dict[str, Any]:
    row = item or {}
    suitability = row.get("suitability") if isinstance(row.get("suitability"), dict) else {}
    content_hash = row.get("content_hash") or row.get("sha256") or suitability.get("sha256")
    return {
        "image_id": row.get("image_id"),
        "content_hash": content_hash,
        "cdn_url": row.get("cdn_url"),
        "role": row.get("role"),
        "order": row.get("order"),
    }


def cache_material(
    *,
    candidate_hash: str | None,
    candidate_url: str | None,
    plan: dict,
    product_info: dict,
    model_version: str,
    prompt_hash: str | None,
) -> dict[str, Any]:
    manifest = (plan.get("reference_manifest") or {}) if isinstance(plan, dict) else {}
    items = list(manifest.get("items") or [])
    primary = next((i for i in items if i.get("role") == "primary_subject"), None)
    supporting = [i for i in items if i.get("role") == "supporting_subject"]
    supporting.sort(key=lambda row: int(row.get("order") or 0))
    logo = plan.get("logo_policy") or {}
    return {
        "candidate_sha256": candidate_hash or "",
        "primary": _ref_entry(primary),
        "supporting": [_ref_entry(row) for row in supporting],
        "manifest_version": manifest.get("version"),
        "manifest_digest": canonical_digest(manifest),
        "logo": {
            "url": product_info.get("logo_url") or product_info.get("brand_logo_url") or logo.get("approved_logo_url"),
            "mode": logo.get("logo_mode"),
            "wordmark": logo.get("wordmark_authority"),
            "version": logo.get("brand_logo_version"),
            "composite": bool(logo.get("use_controlled_compositing")),
        },
        "plan_version": plan.get("version"),
        "plan_digest": canonical_digest(
            {
                "placement": plan.get("placement"),
                "subject": plan.get("subject"),
                "capture_style": plan.get("capture_style"),
                "constraints": plan.get("constraints"),
                "identity_contract": plan.get("identity_contract"),
            }
        ),
        "prompt_sha256": prompt_hash or "",
        "prevention_policy": PREVENTION_POLICY_VERSION,
        "visual_policy": VISUAL_POLICY_VERSION,
        "visual_schema": plan.get("fidelity_policy_version") or VISUAL_POLICY_VERSION,
        "model_version": model_version,
    }


def cache_identity_from_material(material: dict[str, Any]) -> str:
    return canonical_digest(material)


def cache_identity(**kwargs: Any) -> str:
    """Backward-compatible wrapper used by older tests."""
    material = cache_material(
        candidate_hash=kwargs.get("candidate_hash"),
        candidate_url=kwargs.get("candidate_url"),
        plan=kwargs.get("plan") or {},
        product_info=kwargs.get("product_info") or {},
        model_version=kwargs.get("model_version") or "",
        prompt_hash=kwargs.get("prompt_hash"),
    )
    if kwargs.get("primary_ref") and not material["primary"].get("image_id"):
        material["primary"]["image_id"] = kwargs.get("primary_ref")
    return cache_identity_from_material(material)


def _artifact_for(db: Session, run: GenerationRun, index: int) -> GenerationArtifact | None:
    return (
        db.query(GenerationArtifact)
        .filter(
            GenerationArtifact.run_id == run.run_id,
            GenerationArtifact.owner_user_id == run.owner_user_id,
            GenerationArtifact.candidate_index == index,
        )
        .first()
    )


def _composite_logo(plan: dict) -> bool:
    logo = (plan or {}).get("logo_policy") or {}
    return bool(logo.get("use_controlled_compositing") or logo.get("logo_mode") == "composite")


def persist_assessment(
    db: Session,
    run: GenerationRun,
    assessment: VisualFidelityAssessment,
    *,
    cache_key: str,
    composite_logo: bool = False,
    pre_composite: bool = True,
) -> None:
    artifact = _artifact_for(db, run, assessment.candidate_index)
    for check in assessment.checks:
        check = normalize_check(check, composite_logo=composite_logo)
        if check.status == "pass":
            severity, passed = SEV_INFO, True
        elif check.status == "warning":
            severity, passed = SEV_WARNING, True
        elif check.status == "not_verifiable":
            severity, passed = SEV_INFO, True
        else:
            severity, passed = SEV_HARD, False
        details = {
            "candidate_index": assessment.candidate_index,
            "qa_kind": QA_KIND_VISUAL,
            "status": check.status,
            "confidence": check.confidence,
            "short_reason": (check.short_reason or "")[:500],
            "observed_evidence": (check.observed_evidence or "")[:500],
            "reference_evidence": (check.reference_evidence or "")[:500],
            "affected_region": (check.affected_region or "")[:120],
            "publication_effect": check.publication_effect,
            "schema_version": assessment.schema_version,
            "cache_key": cache_key,
            "model_version": assessment.model_version,
            "cache_hit": assessment.cache_hit,
            "correction_used": assessment.correction_used,
            "latency_ms": assessment.latency_ms,
            "prompt_tokens": assessment.prompt_tokens,
            "completion_tokens": assessment.completion_tokens,
            "provider": assessment.provider,
            "pre_composite": pre_composite,
            "composited_output_checked": False,
        }
        if composite_logo and check.check_code in LOGO_CHECK_CODES:
            details["publication_note"] = "logo mismatch warned; overlay not yet applied"
        record_finding(
            db,
            run=run,
            stage=STAGE_POST,
            check_code=check.check_code,
            severity=severity,
            passed=passed,
            details=details,
            artifact_id=artifact.artifact_id if artifact else None,
            qa_kind=QA_KIND_VISUAL,
            confidence=check.confidence,
            visual_model_version=assessment.model_version,
            cache_key=cache_key,
            policy_version=VISUAL_POLICY_VERSION,
        )


def friendly_warning(assessment: VisualFidelityAssessment) -> tuple[str | None, str | None]:
    ordered = sorted(
        assessment.checks,
        key=lambda check: 0 if check.status == "hard_fail" else 1 if check.status == "warning" else 2,
    )
    for check in ordered:
        if check.status in ("hard_fail", "warning"):
            return user_message_for_visual(check.check_code), warning_code_for_visual(check.check_code)
    return None, None


def run_visual_fidelity_qa(
    db: Session,
    product_info: dict,
    *,
    source: str,
    image_urls: list[str],
    assessor: Optional[Callable[[dict[str, Any]], VisualFidelityAssessment]] = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ran": False,
        "calls": 0,
        "correction_calls": 0,
        "cache_hits": 0,
        "warning": None,
        "warning_code": None,
        "hard_fail": False,
        "credits_charged": 0,
        "byok": False,
    }
    task_mode = product_info.get("task_mode") or (
        (product_info.get("generation_provenance") or {}).get("task_mode")
    )
    run_id = product_info.get("generation_run_id")
    owner = product_info.get("owner_user_id")
    if not run_id or not owner:
        return summary
    run = (
        db.query(GenerationRun)
        .filter(GenerationRun.run_id == run_id, GenerationRun.owner_user_id == owner)
        .first()
    )
    if run is None:
        return summary
    if not visual_qa_entitled(owner):
        return summary
    persisted = getattr(run, "visual_fidelity_qa_mode", None)
    if not visual_fidelity_enabled(
        source=source,
        task_mode=task_mode,
        persisted_mode=persisted,
    ):
        return summary
    summary["ran"] = True
    plan = product_info.get("generation_plan") or {}
    manifest_items = list((plan.get("reference_manifest") or {}).get("items") or [])
    primary = next((i for i in manifest_items if i.get("role") == "primary_subject"), None)
    supporting = [i for i in manifest_items if i.get("role") == "supporting_subject"][:2]
    supporting.sort(key=lambda row: int(row.get("order") or 0))
    existing = {
        row.cache_key or ((row.details or {}).get("cache_key") if isinstance(row.details, dict) else None)
        for row in db.query(GenerationArtifactQualityFinding)
        .filter(
            GenerationArtifactQualityFinding.generation_run_id == run.run_id,
            GenerationArtifactQualityFinding.owner_user_id == run.owner_user_id,
            GenerationArtifactQualityFinding.qa_kind == QA_KIND_VISUAL,
        )
        .all()
    }
    existing.discard(None)
    assess = assessor or assess_visual_fidelity
    hashes = product_info.get("_qa_candidate_hashes") or []
    prompt_hash = product_info.get("_sanitized_prompt_hash")
    composite = _composite_logo(plan)
    for index, url in enumerate(image_urls or []):
        cand_hash = hashes[index] if index < len(hashes) else None
        material = cache_material(
            candidate_hash=cand_hash,
            candidate_url=url,
            plan=plan,
            product_info=product_info,
            model_version=visual_qa_model_version(),
            prompt_hash=prompt_hash,
        )
        key = cache_identity_from_material(material)
        if key in existing:
            summary["cache_hits"] += 1
            continue
        payload = {
            "candidate_index": index,
            "candidate_url": url,
            "primary_reference_url": (primary or {}).get("cdn_url"),
            "supporting_reference_urls": [s.get("cdn_url") for s in supporting if s.get("cdn_url")],
            "approved_logo_url": product_info.get("logo_url") or product_info.get("brand_logo_url"),
            "reference_labels": {
                "primary": model_facing_image_label(int((primary or {}).get("order") or 0))
                if primary
                else None,
                "supporting": [
                    model_facing_image_label(int(row.get("order") or 0)) for row in supporting
                ],
            },
            "plan_summary": {
                "placement": plan.get("placement"),
                "subject": plan.get("subject"),
                "capture_style": plan.get("capture_style"),
                "constraints": plan.get("constraints"),
            },
            "logo_policy": plan.get("logo_policy") or {},
            "placement_policy": plan.get("placement"),
            "offering_type": product_info.get("offering_type") or "unknown",
            "asset_intelligence": product_info.get("asset_intelligence_results") or [],
            "composite_logo": composite,
        }
        try:
            assessment = assess(payload)
        except AnalysisFailure as exc:
            logger.warning("visual fidelity QA skipped (adapter failure) run=%s idx=%s", run.run_id, index)
            record_finding(
                db,
                run=run,
                stage=STAGE_POST,
                check_code="visual_qa_unavailable",
                severity=SEV_INFO,
                passed=True,
                details={
                    "candidate_index": index,
                    "qa_kind": QA_KIND_VISUAL,
                    "reason": exc.error_category,
                    "cache_key": key,
                },
                artifact_id=(_artifact_for(db, run, index).artifact_id if _artifact_for(db, run, index) else None),
                qa_kind=QA_KIND_VISUAL,
                cache_key=key,
                policy_version=VISUAL_POLICY_VERSION,
            )
            continue
        assessment.checks = [
            normalize_check(check, composite_logo=composite) for check in assessment.checks
        ]
        assessment.overall_publication_decision = publication_decision_from_checks(assessment.checks)
        summary["calls"] += 1
        if assessment.correction_used:
            summary["correction_calls"] += 1
        if assessment.cache_hit:
            summary["cache_hits"] += 1
        persist_assessment(
            db, run, assessment, cache_key=key, composite_logo=composite, pre_composite=True
        )
        existing.add(key)
        warn, code = friendly_warning(assessment)
        if warn and (
            not summary["warning"]
            or (code != "fidelity_rendered" and summary.get("warning_code") == "fidelity_rendered")
        ):
            if not summary["warning"] or assessment.overall_publication_decision == "blocked":
                summary["warning"] = warn
                summary["warning_code"] = code
        if assessment.overall_publication_decision == "blocked":
            summary["hard_fail"] = True
            if warn:
                summary["warning"] = warn
                summary["warning_code"] = code
        product_info.setdefault("_visual_fidelity_usage", []).append(
            {
                "candidate_index": index,
                "latency_ms": assessment.latency_ms,
                "prompt_tokens": assessment.prompt_tokens,
                "completion_tokens": assessment.completion_tokens,
                "model_version": assessment.model_version,
                "cache_hit": assessment.cache_hit,
                "correction_used": assessment.correction_used,
                "provider": assessment.provider,
            }
        )
    findings = (
        db.query(GenerationArtifactQualityFinding)
        .filter(
            GenerationArtifactQualityFinding.generation_run_id == run.run_id,
            GenerationArtifactQualityFinding.owner_user_id == run.owner_user_id,
        )
        .all()
    )
    eligible = False
    for index, _url in enumerate(image_urls or []):
        artifact = _artifact_for(db, run, index)
        matched = [
            row
            for row in findings
            if (row.details or {}).get("candidate_index") == index
            or (artifact and row.artifact_id == artifact.artifact_id)
        ]
        if candidate_is_eligible(matched):
            eligible = True
            break
    if image_urls and not eligible:
        summary["hard_fail"] = True
    return summary
