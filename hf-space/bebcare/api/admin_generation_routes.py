"""Admin-only generation history and QDS decision timeline."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from bebcare.database import get_db
from bebcare.models.generation_qds import GenerationDecisionEvent, GenerationReferenceSelection
from bebcare.models.generation_run import GenerationRun
from bebcare.models.user import User
from bebcare.schemas.generation_history import (
    GenerationHistoryDetail,
    GenerationHistoryListResponse,
)
from bebcare.services.auth_dependency import get_current_admin_user
from bebcare.services.generation_history_service import (
    get_generation_run_detail,
    list_generation_runs,
)
from bebcare.services.quality_diversity_events import compact_admin_timeline, expanded_admin_timeline

router = APIRouter(prefix="/admin/generation-runs", tags=["admin-generation"])


@router.get("", response_model=GenerationHistoryListResponse)
def list_admin_generation_runs(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str | None = None,
    owner_user_id: str | None = None,
    username: str | None = None,
    email: str | None = None,
    product_id: str | None = None,
    status: str | None = None,
    source: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    has_qa_failures: bool | None = None,
    credits_charged_min: int | None = Query(None, ge=0),
):
    resolved_user_id = user_id or owner_user_id
    return list_generation_runs(
        db,
        page=page,
        page_size=page_size,
        user_id=resolved_user_id,
        username=username,
        email=email,
        product_id=product_id,
        status=status,
        source=source,
        date_from=date_from,
        date_to=date_to,
        has_qa_failures=has_qa_failures,
        credits_charged_min=credits_charged_min,
    )


@router.get("/{run_id}", response_model=GenerationHistoryDetail)
def get_admin_generation_run(
    run_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    detail = get_generation_run_detail(db, run_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Generation run not found")
    return detail


@router.get("/{run_id}/history")
def generation_run_history(
    run_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
    expanded: bool = False,
):
    run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Generation run not found")
    selection = (
        db.query(GenerationReferenceSelection)
        .filter(
            GenerationReferenceSelection.generation_run_id == run_id,
            GenerationReferenceSelection.owner_user_id == run.owner_user_id,
        )
        .first()
    )
    events = (
        db.query(GenerationDecisionEvent)
        .filter(
            GenerationDecisionEvent.generation_run_id == run_id,
            GenerationDecisionEvent.owner_user_id == run.owner_user_id,
        )
        .order_by(GenerationDecisionEvent.sequence_number.asc())
        .all()
    )
    if expanded:
        return expanded_admin_timeline(run, events, selection)
    return compact_admin_timeline(run, events, selection)
