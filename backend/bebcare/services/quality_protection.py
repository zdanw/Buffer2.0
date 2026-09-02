"""Phase 3A deterministic quality protection. No AI QA, no extra provider calls."""

from __future__ import annotations

import hashlib
import logging
from io import BytesIO
from typing import Any

from PIL import Image
from sqlalchemy.orm import Session

from bebcare.models.generation_quality_finding import GenerationArtifactQualityFinding
from bebcare.models.generation_run import GenerationArtifact, GenerationRun
from bebcare.models.product import Product, ProductImage
from bebcare.providers.size_catalog import normalize_size
from bebcare.schemas.generation_plan import (
    group_evidence,
    load_generation_plan,
)
from bebcare.schemas.reference_manifest import (
    MANIFEST_VERSION,
    ReferenceManifest,
    assert_canonical_grounded_order,
)
from bebcare.services.grounded_rollout import GROUNDED_EXECUTED_VERSIONS
from bebcare.services.ownership import stamp_owner
from bebcare.services.quality_candidate_fetch import (
    OUTCOME_INVALID_URL,
    OUTCOME_PERMANENT,
    OUTCOME_RETRIEVED,
    OUTCOME_TEMPORARY,
    OUTCOME_TOO_LARGE,
    fetch_candidate_bytes,
)
from bebcare.services.quality_protection_rollout import (
    POLICY_VERSION,
    quality_blocks_auto_publish,
    quality_protection_enabled,
)

logger = logging.getLogger(__name__)

STAGE_PRE = "pre_generation"
STAGE_POST = "post_generation"
STAGE_PUBLISH = "publish_gate"
SEV_INFO = "info"
SEV_WARNING = "warning"
SEV_HARD = "hard_fail"

MAX_OUTPUT_BYTES = 25 * 1024 * 1024
ASPECT_WARN_RATIO = 0.08
ASPECT_HARD_RATIO = 0.25
FLAT_UNIQUE_COLORS = 3
RETRIEVAL_HARD_OUTCOMES = frozenset({OUTCOME_INVALID_URL, OUTCOME_TOO_LARGE, OUTCOME_PERMANENT})
RETRIEVAL_INELIGIBLE = frozenset(
    {OUTCOME_INVALID_URL, OUTCOME_TOO_LARGE, OUTCOME_PERMANENT, OUTCOME_TEMPORARY}
)
SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
    "authorization",
    "private_key",
)

USER_MESSAGE = {
    "default": "Image could not be validated",
    "unsupported_format": "Image format is invalid",
    "undecodable": "Image format is invalid",
    "aspect_mismatch": "Image size does not match the requested format",
    "publish_blocked": "Automatic publishing paused",
    "candidate_retrieval": "Image could not be retrieved for quality checks",
    "flat_color": "Image has very little color variation",
    "final_prompt_validation_blocked": "The final image prompt still conflicted with product protections",
}


class QualityProtectionError(Exception):
    """Pre-generation hard failure. Do not call the image provider."""

    def __init__(self, message: str, *, check_code: str, error_category: str = "quality_pre_generation"):
        super().__init__(message)
        self.user_message = message
        self.check_code = check_code
        self.error_category = error_category


def user_message_for(check_code: str) -> str:
    return USER_MESSAGE.get(check_code, USER_MESSAGE["default"])


def _secret_leak(value: Any, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            low = str(key).lower()
            if any(frag in low for frag in SECRET_KEY_FRAGMENTS):
                raw = item
                if isinstance(raw, str) and raw.strip():
                    return f"{path}.{key}".strip(".")
            found = _secret_leak(item, f"{path}.{key}".strip("."))
            if found:
                return found
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found = _secret_leak(item, f"{path}[{idx}]")
            if found:
                return found
    return None


def record_finding(
    db: Session,
    *,
    run: GenerationRun,
    stage: str,
    check_code: str,
    severity: str,
    passed: bool,
    details: dict | None = None,
    artifact_id: str | None = None,
    qa_kind: str = "deterministic",
    confidence: str | None = None,
    visual_model_version: str | None = None,
    cache_key: str | None = None,
    policy_version: str | None = None,
) -> GenerationArtifactQualityFinding:
    if artifact_id:
        artifact = (
            db.query(GenerationArtifact)
            .filter(
                GenerationArtifact.artifact_id == artifact_id,
                GenerationArtifact.run_id == run.run_id,
                GenerationArtifact.owner_user_id == run.owner_user_id,
            )
            .first()
        )
        if artifact is None:
            artifact_id = None
    finding = GenerationArtifactQualityFinding(
        artifact_id=artifact_id,
        generation_run_id=run.run_id,
        stage=stage,
        check_code=check_code,
        severity=severity,
        passed=passed,
        details=details or {},
        policy_version=policy_version or POLICY_VERSION,
        qa_kind=qa_kind,
        confidence=confidence,
        visual_model_version=visual_model_version,
        cache_key=cache_key,
    )
    stamp_owner(finding, type("Owner", (), {"user_id": run.owner_user_id})())
    db.add(finding)
    db.flush()
    return finding


def run_has_hard_fail(db: Session, *, owner_user_id: str, run_id: str) -> bool:
    row = (
        db.query(GenerationArtifactQualityFinding)
        .filter(
            GenerationArtifactQualityFinding.generation_run_id == run_id,
            GenerationArtifactQualityFinding.owner_user_id == owner_user_id,
            GenerationArtifactQualityFinding.passed.is_(False),
            GenerationArtifactQualityFinding.severity == SEV_HARD,
        )
        .first()
    )
    return row is not None


def _grounded(product_info: dict) -> bool:
    provenance = product_info.get("generation_provenance") or {}
    executed = (
        product_info.get("executed_pipeline_version")
        or provenance.get("executed_pipeline_version")
        or ""
    )
    return bool(
        product_info.get("grounded_phase1b_enabled")
        or provenance.get("grounded_phase1b_enabled")
        or executed in GROUNDED_EXECUTED_VERSIONS
    )


def _load_run(db: Session, product_info: dict) -> GenerationRun | None:
    run_id = product_info.get("generation_run_id")
    owner = product_info.get("owner_user_id")
    if not run_id or not owner:
        return None
    return (
        db.query(GenerationRun)
        .filter(GenerationRun.run_id == run_id, GenerationRun.owner_user_id == owner)
        .first()
    )


def validate_pre_generation(
    db: Session,
    product_info: dict,
    *,
    source: str,
    provider_ok: bool,
    image_size: str | None,
) -> None:
    task_mode = product_info.get("task_mode") or (
        (product_info.get("generation_provenance") or {}).get("task_mode")
    )
    run = _load_run(db, product_info)
    if run is None:
        if not quality_protection_enabled(source=source, task_mode=task_mode):
            return
        raise QualityProtectionError(
            user_message_for("run_ownership"),
            check_code="run_ownership",
        )
    if not quality_protection_enabled(
        source=source,
        task_mode=task_mode,
        persisted_mode=run.quality_protection_mode,
    ):
        return

    product_id = str(product_info.get("product_id") or "")
    product = (
        db.query(Product)
        .filter(Product.product_id == product_id, Product.owner_user_id == run.owner_user_id)
        .first()
    )
    if not product:
        record_finding(
            db, run=run, stage=STAGE_PRE, check_code="product_ownership",
            severity=SEV_HARD, passed=False, details={"product_id": product_id},
        )
        raise QualityProtectionError(user_message_for("product_ownership"), check_code="product_ownership")

    leak = _secret_leak(product_info.get("generation_plan")) or _secret_leak(
        (product_info.get("generation_provenance") or {}).get("reference_manifest")
    )
    if leak:
        record_finding(
            db, run=run, stage=STAGE_PRE, check_code="secrets_in_provenance",
            severity=SEV_HARD, passed=False, details={"field": leak},
        )
        raise QualityProtectionError(user_message_for("secrets_in_provenance"), check_code="secrets_in_provenance")

    if not provider_ok:
        record_finding(
            db, run=run, stage=STAGE_PRE, check_code="provider_not_configured",
            severity=SEV_HARD, passed=False,
        )
        raise QualityProtectionError(user_message_for("provider_not_configured"), check_code="provider_not_configured")

    if image_size and not normalize_size(image_size):
        record_finding(
            db, run=run, stage=STAGE_PRE, check_code="invalid_output_size",
            severity=SEV_HARD, passed=False, details={"image_size": image_size},
        )
        raise QualityProtectionError(user_message_for("invalid_output_size"), check_code="invalid_output_size")

    grounded = _grounded(product_info)
    raw_manifest = (product_info.get("generation_provenance") or {}).get("reference_manifest")
    if grounded:
        try:
            manifest = ReferenceManifest.model_validate(raw_manifest)
        except Exception:
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="invalid_manifest",
                severity=SEV_HARD, passed=False,
            )
            raise QualityProtectionError(user_message_for("invalid_manifest"), check_code="invalid_manifest")
        if manifest.version != MANIFEST_VERSION:
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="invalid_manifest",
                severity=SEV_HARD, passed=False, details={"version": manifest.version},
            )
            raise QualityProtectionError(user_message_for("invalid_manifest"), check_code="invalid_manifest")
        try:
            assert_canonical_grounded_order(manifest)
        except ValueError as exc:
            code = "duplicate_scene" if "at most one scene" in str(exc) else "canonical_order"
            if "primary_subject" in str(exc):
                code = "missing_primary"
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code=code,
                severity=SEV_HARD, passed=False, details={"reason": str(exc)},
            )
            raise QualityProtectionError(user_message_for(code), check_code=code) from exc
        primaries = [item for item in manifest.items if item.role == "primary_subject"]
        if len(primaries) != 1:
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="missing_primary",
                severity=SEV_HARD, passed=False, details={"primary_count": len(primaries)},
            )
            raise QualityProtectionError(user_message_for("missing_primary"), check_code="missing_primary")
        scenes = [item for item in manifest.items if item.role == "scene"]
        if len(scenes) > 1:
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="duplicate_scene",
                severity=SEV_HARD, passed=False,
            )
            raise QualityProtectionError(user_message_for("duplicate_scene"), check_code="duplicate_scene")

        image_ids = [item.image_id for item in manifest.items if item.image_id]
        for image_id in image_ids:
            owned = (
                db.query(ProductImage)
                .join(Product, Product.product_id == ProductImage.product_id)
                .filter(
                    ProductImage.image_id == image_id,
                    Product.owner_user_id == run.owner_user_id,
                    ProductImage.product_id == product_id,
                )
                .first()
            )
            if owned is None:
                record_finding(
                    db, run=run, stage=STAGE_PRE, check_code="foreign_reference",
                    severity=SEV_HARD, passed=False, details={"image_id": image_id},
                )
                raise QualityProtectionError(
                    user_message_for("foreign_reference"), check_code="foreign_reference"
                )

        plan = load_generation_plan(product_info.get("generation_plan"))
        stored = load_generation_plan(run.generation_plan)
        if plan is None:
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="invalid_plan",
                severity=SEV_HARD, passed=False,
            )
            raise QualityProtectionError(user_message_for("invalid_plan"), check_code="invalid_plan")
        if stored and plan.model_dump() != stored.model_dump():
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="plan_mismatch",
                severity=SEV_HARD, passed=False,
            )
            raise QualityProtectionError(user_message_for("invalid_plan"), check_code="invalid_plan")
        if plan.handheld_physical_replacement != "prohibited" or product_info.get(
            "handheld_physical_replacement"
        ) is True:
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="handheld_physical_enabled",
                severity=SEV_HARD, passed=False,
            )
            raise QualityProtectionError(
                user_message_for("handheld_physical_enabled"),
                check_code="handheld_physical_enabled",
            )
        if "handheld_physical_replacement" not in (plan.forbidden_changes or []):
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="missing_forbidden_rules",
                severity=SEV_HARD, passed=False,
            )
            raise QualityProtectionError(
                user_message_for("missing_forbidden_rules"),
                check_code="missing_forbidden_rules",
            )
        if plan.display_config == "reference_supported_group" and not group_evidence(
            manifest=manifest, structured_group=product_info.get("structured_group")
        ):
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="group_without_evidence",
                severity=SEV_HARD, passed=False,
            )
            raise QualityProtectionError(
                user_message_for("group_without_evidence"),
                check_code="group_without_evidence",
            )
        if plan.subject.duplicate_primary_subjects_allowed:
            record_finding(
                db, run=run, stage=STAGE_PRE, check_code="subject_duplication",
                severity=SEV_HARD, passed=False,
            )
            raise QualityProtectionError(
                user_message_for("subject_duplication"), check_code="subject_duplication"
            )


def _decode_image(raw: bytes) -> tuple[Image.Image | None, str | None]:
    if not raw:
        return None, "empty_image"
    if len(raw) > MAX_OUTPUT_BYTES:
        return None, "file_too_large"
    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except Exception:
        return None, "undecodable"
    fmt = (image.format or "").lower()
    if fmt not in ("jpeg", "jpg", "png", "webp", "gif"):
        return None, "unsupported_format"
    if image.width < 1 or image.height < 1:
        return None, "zero_dimensions"
    return image, None


def _is_low_color(image: Image.Image) -> bool:
    """Few unique colors after downsample. Warning-only in Phase 3A."""
    sample = image.convert("RGB").resize((16, 16), Image.Resampling.NEAREST)
    colors = sample.getcolors(maxcolors=256) or []
    return len(colors) <= FLAT_UNIQUE_COLORS


def _aspect_delta(width: int, height: int, requested: str | None) -> float | None:
    size = normalize_size(requested)
    if not size or not width or not height:
        return None
    rw, rh = (int(part) for part in size.lower().split("x"))
    if rw < 1 or rh < 1:
        return None
    actual = width / height
    expected = rw / rh
    return abs(actual - expected) / expected


def _retrieval_finding(outcome: str, details: dict | None = None) -> dict[str, Any]:
    hard = outcome in RETRIEVAL_HARD_OUTCOMES
    return {
        "check_code": "candidate_retrieval",
        "severity": SEV_HARD if hard else SEV_WARNING,
        "passed": False,
        "details": {"outcome": outcome, **(details or {})},
    }


def inspect_candidate_bytes(
    raw: bytes | None,
    *,
    requested_size: str | None = None,
    source_hashes: set[str] | None = None,
    seen_hashes: set[str] | None = None,
    allow_source_reuse: bool = False,
    retrieval_outcome: str | None = None,
    retrieval_details: dict | None = None,
) -> list[dict[str, Any]]:
    """Return finding dicts (not persisted). Used by post-generation and tests."""
    findings: list[dict[str, Any]] = []
    if retrieval_outcome and retrieval_outcome != OUTCOME_RETRIEVED:
        return [_retrieval_finding(retrieval_outcome, retrieval_details)]
    if raw is None:
        return [{"check_code": "missing_candidate", "severity": SEV_HARD, "passed": False, "details": {}}]
    image, fail = _decode_image(raw)
    if fail:
        code = fail if fail != "empty_image" else "empty_image"
        return [{"check_code": code, "severity": SEV_HARD, "passed": False, "details": {"bytes": len(raw)}}]
    digest = hashlib.sha256(raw).hexdigest()
    findings.append(
        {
            "check_code": "candidate_hash",
            "severity": SEV_INFO,
            "passed": True,
            "details": {"sha256": digest, "width": image.width, "height": image.height},
        }
    )
    if _is_low_color(image):
        findings.append(
            {
                "check_code": "flat_color",
                "severity": SEV_WARNING,
                "passed": True,
                "details": {"width": image.width, "height": image.height},
            }
        )
    delta = _aspect_delta(image.width, image.height, requested_size)
    if delta is not None and delta > ASPECT_HARD_RATIO:
        findings.append(
            {
                "check_code": "aspect_mismatch",
                "severity": SEV_HARD,
                "passed": False,
                "details": {"delta": round(delta, 4)},
            }
        )
    elif delta is not None and delta > ASPECT_WARN_RATIO:
        findings.append(
            {
                "check_code": "aspect_mismatch",
                "severity": SEV_WARNING,
                "passed": True,
                "details": {"delta": round(delta, 4)},
            }
        )
    if seen_hashes is not None and digest in seen_hashes:
        findings.append(
            {
                "check_code": "duplicate_candidate",
                "severity": SEV_WARNING,
                "passed": True,
                "details": {"sha256": digest},
            }
        )
    if source_hashes and digest in source_hashes and not allow_source_reuse:
        findings.append(
            {
                "check_code": "source_identical",
                "severity": SEV_HARD,
                "passed": False,
                "details": {"sha256": digest},
            }
        )
    if seen_hashes is not None:
        seen_hashes.add(digest)
    return findings


def bind_findings_to_artifacts(db: Session, run: GenerationRun) -> None:
    artifacts = (
        db.query(GenerationArtifact)
        .filter(
            GenerationArtifact.run_id == run.run_id,
            GenerationArtifact.owner_user_id == run.owner_user_id,
        )
        .all()
    )
    by_index = {int(row.candidate_index): row for row in artifacts}
    rows = (
        db.query(GenerationArtifactQualityFinding)
        .filter(
            GenerationArtifactQualityFinding.generation_run_id == run.run_id,
            GenerationArtifactQualityFinding.owner_user_id == run.owner_user_id,
            GenerationArtifactQualityFinding.artifact_id.is_(None),
            GenerationArtifactQualityFinding.stage == STAGE_POST,
        )
        .all()
    )
    for finding in rows:
        details = finding.details if isinstance(finding.details, dict) else {}
        index = details.get("candidate_index")
        if index is None:
            continue
        artifact = by_index.get(int(index))
        if artifact is not None:
            finding.artifact_id = artifact.artifact_id


def _owned_post_findings(db: Session, run: GenerationRun) -> list[GenerationArtifactQualityFinding]:
    return (
        db.query(GenerationArtifactQualityFinding)
        .filter(
            GenerationArtifactQualityFinding.generation_run_id == run.run_id,
            GenerationArtifactQualityFinding.owner_user_id == run.owner_user_id,
            GenerationArtifactQualityFinding.stage == STAGE_POST,
        )
        .all()
    )


def _findings_for_index(
    findings: list[GenerationArtifactQualityFinding],
    *,
    index: int,
    artifact_id: str | None,
) -> list[GenerationArtifactQualityFinding]:
    matched = []
    for row in findings:
        if artifact_id and row.artifact_id == artifact_id:
            matched.append(row)
            continue
        details = row.details if isinstance(row.details, dict) else {}
        if details.get("candidate_index") == index:
            matched.append(row)
    return matched


def candidate_is_eligible(findings: list[GenerationArtifactQualityFinding]) -> bool:
    if not findings:
        return True
    for row in findings:
        if row.severity == SEV_HARD and not row.passed:
            return False
        details = row.details if isinstance(row.details, dict) else {}
        if row.check_code == "candidate_retrieval":
            outcome = details.get("outcome")
            if outcome in RETRIEVAL_INELIGIBLE:
                return False
    return True


def _mark_selected_artifact(
    db: Session, run: GenerationRun, artifact: GenerationArtifact | None
) -> None:
    for row in run.artifacts or []:
        if row.owner_user_id != run.owner_user_id:
            row.selected = False
            continue
        row.selected = bool(artifact is not None and row.artifact_id == artifact.artifact_id)
    db.flush()


def validate_post_generation(
    db: Session,
    product_info: dict,
    *,
    source: str,
    image_urls: list[str],
    requested_size: str | None,
    candidate_bytes: list[bytes | None] | None = None,
    source_reference_bytes: list[bytes] | None = None,
) -> dict[str, Any]:
    """Persist post-generation findings. Never calls an image model."""
    summary: dict[str, Any] = {
        "hard_fail": False,
        "warning": None,
        "check_codes": [],
        "candidates": [],
        "selected_index": None,
    }
    task_mode = product_info.get("task_mode") or (
        (product_info.get("generation_provenance") or {}).get("task_mode")
    )
    run = _load_run(db, product_info)
    if run is None:
        return summary
    if not quality_protection_enabled(
        source=source,
        task_mode=task_mode,
        persisted_mode=run.quality_protection_mode,
    ):
        return summary
    source_hashes = {hashlib.sha256(blob).hexdigest() for blob in (source_reference_bytes or []) if blob}
    seen: set[str] = set()
    allow_reuse = not _grounded(product_info)
    blobs = candidate_bytes
    if not image_urls:
        record_finding(
            db, run=run, stage=STAGE_POST, check_code="missing_candidate",
            severity=SEV_HARD, passed=False, details={"candidate_index": None},
        )
        summary["hard_fail"] = True
        summary["warning"] = user_message_for("missing_candidate")
        summary["check_codes"].append("missing_candidate")
        return summary
    eligible_indexes: list[int] = []
    any_hard = False
    for index, url in enumerate(image_urls):
        artifact_id = None
        if run.artifacts:
            for artifact in run.artifacts:
                if artifact.candidate_index == index and artifact.owner_user_id == run.owner_user_id:
                    artifact_id = artifact.artifact_id
                    break
        candidate_meta = {
            "index": index,
            "eligible": True,
            "hard_fail": False,
            "retrieval_outcome": None,
        }
        items: list[dict[str, Any]] = []
        if url in (None, ""):
            items = [{
                "check_code": "missing_candidate",
                "severity": SEV_HARD,
                "passed": False,
                "details": {},
            }]
        else:
            raw = blobs[index] if blobs is not None and index < len(blobs) else None
            retrieval_outcome = None
            retrieval_details = None
            if raw is None:
                fetched = fetch_candidate_bytes(url)
                retrieval_outcome = fetched.outcome
                retrieval_details = fetched.details
                raw = fetched.content
                candidate_meta["retrieval_outcome"] = retrieval_outcome
            items = inspect_candidate_bytes(
                raw,
                requested_size=requested_size,
                source_hashes=source_hashes,
                seen_hashes=seen,
                allow_source_reuse=allow_reuse,
                retrieval_outcome=retrieval_outcome,
                retrieval_details=retrieval_details,
            )
            for item in items:
                if item.get("check_code") == "candidate_hash":
                    candidate_meta["sha256"] = (item.get("details") or {}).get("sha256")
        recorded: list[GenerationArtifactQualityFinding] = []
        for item in items:
            details = dict(item.get("details") or {})
            details["candidate_index"] = index
            recorded.append(
                record_finding(
                    db,
                    run=run,
                    stage=STAGE_POST,
                    check_code=item["check_code"],
                    severity=item["severity"],
                    passed=item["passed"],
                    details=details,
                    artifact_id=artifact_id,
                )
            )
            if item["severity"] == SEV_HARD and not item["passed"]:
                any_hard = True
                candidate_meta["hard_fail"] = True
                summary["check_codes"].append(item["check_code"])
                if not summary["warning"]:
                    summary["warning"] = user_message_for(item["check_code"])
            elif item["severity"] == SEV_WARNING and not summary["warning"]:
                summary["warning"] = user_message_for(item["check_code"])
        eligible = candidate_is_eligible(recorded)
        candidate_meta["eligible"] = eligible
        if eligible:
            eligible_indexes.append(index)
        summary["candidates"].append(candidate_meta)
    summary["selected_index"] = eligible_indexes[0] if eligible_indexes else None
    summary["hard_fail"] = (not eligible_indexes) or (any_hard and not eligible_indexes)
    if not eligible_indexes:
        summary["hard_fail"] = True
    return summary


def apply_publish_gate(
    db: Session,
    *,
    owner_user_id: str,
    run_id: str | None,
    source: str,
    task_mode: str | None,
    hard_fail: bool = False,
    image_urls: list[str] | None = None,
) -> dict[str, Any]:
    del hard_fail
    empty = {
        "blocked": False,
        "warning": None,
        "selected_url": (image_urls or [None])[0] if image_urls else None,
        "selected_artifact_id": None,
        "selected_index": 0 if image_urls else None,
    }
    if not run_id:
        return empty
    run = (
        db.query(GenerationRun)
        .filter(GenerationRun.run_id == run_id, GenerationRun.owner_user_id == owner_user_id)
        .first()
    )
    if run is None:
        return {**empty, "selected_url": None, "selected_index": None}

    bind_findings_to_artifacts(db, run)
    artifacts = sorted(
        db.query(GenerationArtifact)
        .filter(
            GenerationArtifact.run_id == run.run_id,
            GenerationArtifact.owner_user_id == run.owner_user_id,
        )
        .all(),
        key=lambda row: int(row.candidate_index),
    )
    run.artifacts = artifacts
    urls = list(image_urls) if image_urls is not None else [row.cdn_url for row in artifacts]
    findings = _owned_post_findings(db, run)
    blocking = quality_blocks_auto_publish(
        source=source,
        task_mode=task_mode,
        persisted_mode=run.quality_protection_mode,
    )
    from bebcare.services.product_fidelity_rollout import visual_fidelity_blocks_auto_publish

    blocking = blocking or visual_fidelity_blocks_auto_publish(
        source=source,
        task_mode=task_mode,
        persisted_mode=getattr(run, "visual_fidelity_qa_mode", None),
    )

    def _artifact_for_index(index: int) -> GenerationArtifact | None:
        for row in artifacts:
            if int(row.candidate_index) == index:
                return row
        return None

    if not blocking:
        chosen = _artifact_for_index(0) if artifacts else None
        url = urls[0] if urls else (chosen.cdn_url if chosen else None)
        _mark_selected_artifact(db, run, chosen)
        return {
            "blocked": False,
            "warning": None,
            "selected_url": url,
            "selected_artifact_id": chosen.artifact_id if chosen else None,
            "selected_index": 0 if url else None,
        }

    selected_index = None
    selected_artifact = None
    selected_url = None
    for index, url in enumerate(urls):
        artifact = _artifact_for_index(index)
        matched = _findings_for_index(
            findings, index=index, artifact_id=artifact.artifact_id if artifact else None
        )
        if candidate_is_eligible(matched):
            selected_index = index
            selected_artifact = artifact
            selected_url = url
            break

    if selected_url:
        _mark_selected_artifact(db, run, selected_artifact)
        return {
            "blocked": False,
            "warning": None,
            "selected_url": selected_url,
            "selected_artifact_id": selected_artifact.artifact_id if selected_artifact else None,
            "selected_index": selected_index,
        }

    record_finding(
        db,
        run=run,
        stage=STAGE_PUBLISH,
        check_code="publish_blocked",
        severity=SEV_HARD,
        passed=False,
        details={"task_mode": task_mode},
    )
    _mark_selected_artifact(db, run, None)
    return {
        "blocked": True,
        "warning": user_message_for("publish_blocked"),
        "selected_url": None,
        "selected_artifact_id": None,
        "selected_index": None,
    }
