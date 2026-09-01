from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, exists
from sqlalchemy.orm import Session, selectinload

from bebcare.models.generate_task import GenerateTask
from bebcare.models.generation_quality_finding import GenerationArtifactQualityFinding
from bebcare.models.generation_run import GenerationArtifact, GenerationRun
from bebcare.models.image_credit import ImageCreditGrant, ImageCreditReservation
from bebcare.models.product import Product
from bebcare.models.user import User
from bebcare.schemas.generation_history import (
    GenerationHistoryArtifact,
    GenerationHistoryCompareSibling,
    GenerationHistoryCreditInfo,
    GenerationHistoryDetail,
    GenerationHistoryFinding,
    GenerationHistoryGenerateTask,
    GenerationHistoryListItem,
    GenerationHistoryListResponse,
    GenerationHistoryProductSummary,
    GenerationHistoryQaSummary,
    GenerationHistoryUserSummary,
)

CHECK_CODE_LABELS: dict[str, str] = {
    "run_ownership": "Run ownership",
    "product_ownership": "Product ownership",
    "secrets_in_provenance": "Secrets in provenance",
    "provider_not_configured": "Provider not configured",
    "invalid_output_size": "Invalid output size",
    "invalid_manifest": "Invalid reference manifest",
    "canonical_order": "Reference order invalid",
    "missing_primary": "Missing primary reference",
    "duplicate_scene": "Duplicate scene reference",
    "foreign_reference": "Foreign reference image",
    "invalid_plan": "Invalid generation plan",
    "plan_mismatch": "Plan mismatch",
    "handheld_physical_enabled": "Handheld physical replacement",
    "missing_forbidden_rules": "Missing forbidden rules",
    "group_without_evidence": "Group without evidence",
    "subject_duplication": "Subject duplication",
    "candidate_retrieval": "Candidate retrieval",
    "missing_candidate": "Missing candidate image",
    "unsupported_format": "Unsupported image format",
    "undecodable": "Undecodable image",
    "empty_image": "Empty image",
    "candidate_hash": "Candidate hash mismatch",
    "flat_color": "Flat color image",
    "aspect_mismatch": "Aspect ratio mismatch",
    "duplicate_candidate": "Duplicate candidate",
    "source_identical": "Identical to source",
    "visual_qa_unavailable": "Visual QA unavailable",
    "publish_blocked": "Publish blocked",
    "base_or_housing_redesign": "Product base/housing redesigned",
    "invented_logo": "Invented logo or branding",
    "generic_ai_lifestyle_staging": "Generic AI lifestyle staging",
    "total_reference_identity_loss": "Lost reference identity",
    "generated_small_text": "Generated small text",
}


def _check_label(code: str) -> str:
    return CHECK_CODE_LABELS.get(code, code.replace("_", " ").title())


def _qa_summary_for_run(db: Session, run_id: str) -> GenerationHistoryQaSummary:
    rows = (
        db.query(GenerationArtifactQualityFinding.severity, GenerationArtifactQualityFinding.passed)
        .filter(
            GenerationArtifactQualityFinding.generation_run_id == run_id,
            GenerationArtifactQualityFinding.passed.is_(False),
        )
        .all()
    )
    hard_fail = sum(1 for severity, _ in rows if severity == "hard_fail")
    warning = sum(1 for severity, _ in rows if severity == "warning")
    return GenerationHistoryQaSummary(hard_fail_count=hard_fail, warning_count=warning)


def _provider_summary(run: GenerationRun) -> Optional[str]:
    parts: list[str] = []
    if run.model:
        parts.append(run.model)
    if run.image_provider_mode:
        parts.append(run.image_provider_mode)
    return " · ".join(parts) if parts else None


def _status_label(status: str) -> str:
    return status.replace("_", " ").title()


def _source_label(source: str) -> str:
    return "Studio" if source == "studio" else source.replace("_", " ").title()


def build_diagnosis_line(
    run: GenerationRun,
    qa_summary: GenerationHistoryQaSummary,
    *,
    top_finding_code: Optional[str] = None,
    ref_count: int = 0,
) -> str:
    parts: list[str] = [_status_label(run.status)]
    if run.credits_charged:
        credit_word = "credit" if run.credits_charged == 1 else "credits"
        parts.append(f"{run.credits_charged} {credit_word} charged")
    else:
        parts.append("0 credits charged")
    parts.append(_source_label(run.source))
    if run.image_provider_mode:
        mode = "Platform" if run.image_provider_mode == "platform" else run.image_provider_mode.upper()
        parts.append(f"{mode} provider")
    if qa_summary.hard_fail_count:
        code = top_finding_code or "quality issue"
        parts.append(f"QA hard fail: {_check_label(code)}")
    elif qa_summary.warning_count:
        code = top_finding_code or "quality warning"
        parts.append(f"QA warning: {_check_label(code)}")
    if run.executed_pipeline_version:
        parts.append(f"Pipeline: {run.executed_pipeline_version}")
    if ref_count:
        ref_word = "reference" if ref_count == 1 else "references"
        parts.append(f"{ref_count} {ref_word} used")
    return " · ".join(parts)


def _user_summary(user: User) -> GenerationHistoryUserSummary:
    return GenerationHistoryUserSummary(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
    )


def _product_summary(product: Optional[Product]) -> Optional[GenerationHistoryProductSummary]:
    if not product:
        return None
    return GenerationHistoryProductSummary(
        product_id=product.product_id,
        name=product.product_name,
    )


def _thumbnail_from_artifacts(artifacts: list[GenerationArtifact]) -> Optional[str]:
    if not artifacts:
        return None
    ordered = sorted(artifacts, key=lambda row: row.candidate_index)
    return ordered[0].cdn_url


def _credit_info(db: Session, run: GenerationRun) -> GenerationHistoryCreditInfo:
    if not run.generate_task_id:
        return GenerationHistoryCreditInfo(charged=run.credits_charged or 0)
    reservation = (
        db.query(ImageCreditReservation)
        .filter(ImageCreditReservation.generate_task_id == run.generate_task_id)
        .first()
    )
    if not reservation:
        return GenerationHistoryCreditInfo(charged=run.credits_charged or 0)
    grant = db.query(ImageCreditGrant).filter(ImageCreditGrant.id == reservation.grant_id).first()
    return GenerationHistoryCreditInfo(
        charged=run.credits_charged or 0,
        reservation_status=reservation.status,
        grant_source=grant.source if grant else None,
        grant_note=grant.note if grant else None,
    )


def _serialize_finding(row: GenerationArtifactQualityFinding) -> GenerationHistoryFinding:
    return GenerationHistoryFinding(
        finding_id=row.finding_id,
        stage=row.stage,
        check_code=row.check_code,
        check_label=_check_label(row.check_code),
        severity=row.severity,
        passed=row.passed,
        details=row.details if isinstance(row.details, dict) else None,
        qa_kind=row.qa_kind,
        confidence=row.confidence,
        created_at=row.created_at,
    )


def _ref_count(run: GenerationRun) -> int:
    manifest = run.reference_manifest if isinstance(run.reference_manifest, dict) else {}
    items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    if items:
        return len(items)
    snapshot = run.output_snapshot if isinstance(run.output_snapshot, dict) else {}
    product_refs = snapshot.get("reference_product_images") or []
    scene_refs = snapshot.get("reference_scene_images") or []
    return len(product_refs) + len(scene_refs)


def _top_finding_code(db: Session, run_id: str) -> Optional[str]:
    row = (
        db.query(GenerationArtifactQualityFinding.check_code)
        .filter(
            GenerationArtifactQualityFinding.generation_run_id == run_id,
            GenerationArtifactQualityFinding.passed.is_(False),
        )
        .order_by(
            GenerationArtifactQualityFinding.severity.desc(),
            GenerationArtifactQualityFinding.created_at.desc(),
        )
        .first()
    )
    return row[0] if row else None


def list_generation_runs(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    has_qa_failures: Optional[bool] = None,
    credits_charged_min: Optional[int] = None,
) -> GenerationHistoryListResponse:
    query = (
        db.query(GenerationRun)
        .join(User, User.user_id == GenerationRun.owner_user_id)
        .outerjoin(Product, Product.product_id == GenerationRun.product_id)
        .options(selectinload(GenerationRun.artifacts))
    )

    if user_id:
        query = query.filter(GenerationRun.owner_user_id == user_id)
    if username:
        query = query.filter(User.username.ilike(f"%{username.strip()}%"))
    if email:
        query = query.filter(User.email.ilike(f"%{email.strip()}%"))
    if product_id:
        query = query.filter(GenerationRun.product_id == product_id)
    if status:
        query = query.filter(GenerationRun.status == status)
    if source:
        query = query.filter(GenerationRun.source == source)
    if date_from:
        query = query.filter(GenerationRun.created_at >= date_from)
    if date_to:
        query = query.filter(GenerationRun.created_at <= date_to)
    if credits_charged_min is not None:
        query = query.filter(GenerationRun.credits_charged >= credits_charged_min)
    if has_qa_failures is True:
        query = query.filter(
            exists().where(
                and_(
                    GenerationArtifactQualityFinding.generation_run_id == GenerationRun.run_id,
                    GenerationArtifactQualityFinding.passed.is_(False),
                    GenerationArtifactQualityFinding.severity.in_(("hard_fail", "warning")),
                )
            )
        )
    elif has_qa_failures is False:
        query = query.filter(
            ~exists().where(
                and_(
                    GenerationArtifactQualityFinding.generation_run_id == GenerationRun.run_id,
                    GenerationArtifactQualityFinding.passed.is_(False),
                    GenerationArtifactQualityFinding.severity.in_(("hard_fail", "warning")),
                )
            )
        )

    total = query.with_entities(GenerationRun.run_id).distinct().count()
    offset = (page - 1) * page_size
    rows = (
        query.order_by(GenerationRun.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    user_ids = {run.owner_user_id for run in rows}
    users = {
        row.user_id: row
        for row in db.query(User).filter(User.user_id.in_(user_ids)).all()
    } if user_ids else {}

    product_ids = {run.product_id for run in rows if run.product_id}
    products = {
        row.product_id: row
        for row in db.query(Product).filter(Product.product_id.in_(product_ids)).all()
    } if product_ids else {}

    items: list[GenerationHistoryListItem] = []
    for run in rows:
        user = users.get(run.owner_user_id)
        if not user:
            continue
        qa_summary = _qa_summary_for_run(db, run.run_id)
        top_code = _top_finding_code(db, run.run_id) if qa_summary.hard_fail_count or qa_summary.warning_count else None
        items.append(
            GenerationHistoryListItem(
                run_id=run.run_id,
                created_at=run.created_at,
                status=run.status,
                source=run.source,
                user=_user_summary(user),
                product=_product_summary(products.get(run.product_id)) if run.product_id else None,
                thumbnail_url=_thumbnail_from_artifacts(list(run.artifacts or [])),
                credits_charged=run.credits_charged or 0,
                latency_ms=run.latency_ms,
                provider_summary=_provider_summary(run),
                qa_summary=qa_summary,
                diagnosis_line=build_diagnosis_line(
                    run,
                    qa_summary,
                    top_finding_code=top_code,
                    ref_count=_ref_count(run),
                ),
            )
        )

    pages = max(1, (total + page_size - 1) // page_size)
    return GenerationHistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def get_generation_run_detail(db: Session, run_id: str) -> Optional[GenerationHistoryDetail]:
    run = (
        db.query(GenerationRun)
        .options(selectinload(GenerationRun.artifacts))
        .filter(GenerationRun.run_id == run_id)
        .first()
    )
    if not run:
        return None

    user = db.query(User).filter(User.user_id == run.owner_user_id).first()
    if not user:
        return None

    product = None
    if run.product_id:
        product = db.query(Product).filter(Product.product_id == run.product_id).first()

    findings = (
        db.query(GenerationArtifactQualityFinding)
        .filter(GenerationArtifactQualityFinding.generation_run_id == run.run_id)
        .order_by(
            GenerationArtifactQualityFinding.stage.asc(),
            GenerationArtifactQualityFinding.created_at.asc(),
        )
        .all()
    )
    qa_summary = _qa_summary_for_run(db, run.run_id)
    top_code = _top_finding_code(db, run.run_id) if qa_summary.hard_fail_count or qa_summary.warning_count else None

    generate_task_info: Optional[GenerationHistoryGenerateTask] = None
    if run.generate_task_id:
        task = db.query(GenerateTask).filter(GenerateTask.task_id == run.generate_task_id).first()
        if task:
            generate_task_info = GenerationHistoryGenerateTask(
                task_id=task.task_id,
                status=task.status,
                progress=task.progress or 0,
                stage=task.stage,
                result=task.result if isinstance(task.result, dict) else None,
                expired=False,
            )
        else:
            generate_task_info = GenerationHistoryGenerateTask(
                task_id=run.generate_task_id,
                status="EXPIRED",
                expired=True,
            )

    compare_siblings: list[GenerationHistoryCompareSibling] = []
    if run.compare_group_id:
        siblings = (
            db.query(GenerationRun)
            .options(selectinload(GenerationRun.artifacts))
            .filter(
                GenerationRun.compare_group_id == run.compare_group_id,
                GenerationRun.run_id != run.run_id,
            )
            .order_by(GenerationRun.created_at.asc())
            .all()
        )
        for sibling in siblings:
            selected = any(artifact.selected for artifact in (sibling.artifacts or []))
            compare_siblings.append(
                GenerationHistoryCompareSibling(
                    run_id=sibling.run_id,
                    status=sibling.status,
                    image_prompt_pipeline=sibling.image_prompt_pipeline,
                    thumbnail_url=_thumbnail_from_artifacts(list(sibling.artifacts or [])),
                    selected=selected,
                    created_at=sibling.created_at,
                )
            )

    artifacts = [
        GenerationHistoryArtifact(
            artifact_id=artifact.artifact_id,
            cdn_url=artifact.cdn_url,
            selected=artifact.selected,
            persistence_warning=artifact.persistence_warning,
            candidate_index=artifact.candidate_index,
        )
        for artifact in sorted(run.artifacts or [], key=lambda row: row.candidate_index)
    ]

    from bebcare.services.generation_diagnostics import diagnostics_for_run

    diag = diagnostics_for_run(db, run, include_technical=True)
    return GenerationHistoryDetail(
        run_id=run.run_id,
        owner_user_id=run.owner_user_id,
        source=run.source,
        product_id=run.product_id,
        scheduled_task_id=run.scheduled_task_id,
        generate_task_id=run.generate_task_id,
        rollout_mode_at_start=run.rollout_mode_at_start,
        experiment_variant=run.experiment_variant,
        requested_pipeline_version=run.requested_pipeline_version,
        executed_pipeline_version=run.executed_pipeline_version,
        fallback_reason=run.fallback_reason,
        fallback_path=run.fallback_path,
        image_prompt_pipeline=run.image_prompt_pipeline,
        compare_group_id=run.compare_group_id,
        provider_type=run.provider_type,
        provider_id=run.provider_id,
        model=run.model,
        image_size=run.image_size,
        image_provider_mode=run.image_provider_mode,
        status=run.status,
        error_category=run.error_category,
        latency_ms=run.latency_ms,
        retry_count=run.retry_count,
        credits_charged=run.credits_charged or 0,
        provider_usage=run.provider_usage if isinstance(run.provider_usage, dict) else None,
        created_at=run.created_at,
        completed_at=run.completed_at,
        quality_protection_mode=run.quality_protection_mode,
        quality_policy_version=run.quality_policy_version,
        product_fidelity_prevention_mode=run.product_fidelity_prevention_mode,
        visual_fidelity_qa_mode=run.visual_fidelity_qa_mode,
        visual_fidelity_policy_version=run.visual_fidelity_policy_version,
        requested_selector_strategy=run.requested_selector_strategy,
        executed_selector_strategy=run.executed_selector_strategy,
        selection_seed=run.selection_seed,
        user=_user_summary(user),
        product=_product_summary(product),
        output_snapshot=run.output_snapshot if isinstance(run.output_snapshot, dict) else None,
        generate_task=generate_task_info,
        artifacts=artifacts,
        quality_findings=[_serialize_finding(row) for row in findings],
        credit=_credit_info(db, run),
        generation_plan=run.generation_plan if isinstance(run.generation_plan, dict) else None,
        reference_manifest=run.reference_manifest if isinstance(run.reference_manifest, dict) else None,
        qa_summary=qa_summary,
        diagnosis_line=build_diagnosis_line(
            run,
            qa_summary,
            top_finding_code=top_code,
            ref_count=_ref_count(run),
        ),
        compare_siblings=compare_siblings,
        generation_diagnostics=diag.model_dump(),
    )
