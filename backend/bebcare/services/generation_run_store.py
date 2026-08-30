from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from bebcare.database import SessionLocal
from bebcare.models.generation_run import GenerationArtifact, GenerationRun
from bebcare.models.image_credit import ImageCreditReservation
from bebcare.services.ownership import stamp_owner


def create_generation_run(
    db: Session,
    *,
    owner_user_id: str,
    source: str,
    product_id: Optional[str],
    generate_task_id: Optional[str],
    scheduled_task_id: Optional[str] = None,
    rollout_mode_at_start: str,
    experiment_variant: Optional[str],
    requested_pipeline_version: str,
    executed_pipeline_version: str,
    fallback_reason: Optional[str],
    fallback_path: Optional[str],
    image_prompt_pipeline: Optional[str],
    compare_group_id: Optional[str],
    reference_manifest: Optional[dict],
    provider_id: Optional[str],
    model: Optional[str],
    image_size: Optional[str],
    image_provider_mode: Optional[str],
    provider_type: Optional[str] = None,
) -> GenerationRun:
    run = GenerationRun(
        source=source,
        product_id=product_id,
        scheduled_task_id=scheduled_task_id,
        generate_task_id=generate_task_id,
        rollout_mode_at_start=rollout_mode_at_start,
        experiment_variant=experiment_variant,
        requested_pipeline_version=requested_pipeline_version,
        executed_pipeline_version=executed_pipeline_version,
        fallback_reason=fallback_reason,
        fallback_path=fallback_path,
        image_prompt_pipeline=image_prompt_pipeline,
        compare_group_id=compare_group_id,
        reference_manifest=reference_manifest,
        provider_type=provider_type,
        provider_id=provider_id,
        model=model,
        image_size=image_size,
        image_provider_mode=image_provider_mode,
        status="pending",
        credits_charged=0,
    )
    stamp_owner(run, type("Owner", (), {"user_id": owner_user_id})())
    db.add(run)
    db.flush()
    return run


def add_artifacts(
    db: Session,
    run: GenerationRun,
    image_urls: list[str],
    *,
    persistence_warning: Optional[str] = None,
) -> None:
    existing = {row.candidate_index for row in (run.artifacts or [])}
    for index, url in enumerate(image_urls or []):
        if not url or index in existing:
            continue
        artifact = GenerationArtifact(
            run_id=run.run_id,
            candidate_index=index,
            cdn_url=url,
            selected=False,
            persistence_warning=persistence_warning,
        )
        stamp_owner(artifact, type("Owner", (), {"user_id": run.owner_user_id})())
        db.add(artifact)


def credits_charged_for_task(db: Session, generate_task_id: Optional[str]) -> int:
    if not generate_task_id:
        return 0
    row = (
        db.query(ImageCreditReservation)
        .filter(
            ImageCreditReservation.generate_task_id == generate_task_id,
            ImageCreditReservation.status == "confirmed",
        )
        .first()
    )
    return int(row.amount) if row else 0


def finish_generation_run(
    db: Session,
    run: GenerationRun,
    *,
    status: str,
    error_category: Optional[str] = None,
    latency_ms: Optional[int] = None,
    image_urls: Optional[list[str]] = None,
    persistence_warning: Optional[str] = None,
    provider_usage: Optional[dict] = None,
    retry_count: Optional[int] = None,
) -> None:
    run.status = status
    run.completed_at = datetime.utcnow()
    if error_category is not None:
        run.error_category = error_category
    if latency_ms is not None:
        run.latency_ms = latency_ms
    if provider_usage is not None:
        run.provider_usage = provider_usage
    if retry_count is not None:
        run.retry_count = retry_count
    run.credits_charged = credits_charged_for_task(db, run.generate_task_id)
    if image_urls:
        add_artifacts(db, run, image_urls, persistence_warning=persistence_warning)
    elif persistence_warning and run.artifacts:
        for artifact in run.artifacts:
            artifact.persistence_warning = persistence_warning


def sync_runs_for_generate_task(
    db: Session,
    generate_task_id: str,
    *,
    status: Optional[str],
    result: Any = None,
) -> None:
    rows = (
        db.query(GenerationRun)
        .filter(GenerationRun.generate_task_id == generate_task_id)
        .all()
    )
    if not rows:
        return
    mapped = None
    error_category = None
    image_urls: list[str] = []
    warning = None
    if status == "SUCCESS":
        mapped = "succeeded"
        if isinstance(result, dict):
            image = result.get("image")
            if image:
                image_urls = [image]
            warning = result.get("warning")
    elif status in ("FAILURE", "FAILED", "CANCELLED"):
        mapped = "failed"
        if isinstance(result, dict) and result.get("error"):
            error_category = "generate_task_failed"
    if mapped is None:
        return
    for run in rows:
        if run.status in ("succeeded", "failed", "cancelled") and mapped == run.status:
            if image_urls:
                add_artifacts(db, run, image_urls, persistence_warning=warning)
            continue
        finish_generation_run(
            db,
            run,
            status=mapped,
            error_category=error_category,
            image_urls=image_urls,
            persistence_warning=warning,
        )


def fail_runs_for_generate_task(db: Session, generate_task_id: str, error_category: str) -> None:
    rows = (
        db.query(GenerationRun)
        .filter(
            GenerationRun.generate_task_id == generate_task_id,
            GenerationRun.status.in_(("pending", "running")),
        )
        .all()
    )
    for run in rows:
        finish_generation_run(db, run, status="failed", error_category=error_category)


def create_run_in_own_session(**kwargs) -> str:
    db = SessionLocal()
    try:
        run = create_generation_run(db, **kwargs)
        db.commit()
        return run.run_id
    finally:
        db.close()
