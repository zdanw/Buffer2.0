"""Admin-only generation decision history. No ordinary-user workflow."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from bebcare.database import get_db
from bebcare.models.generation_qds import GenerationDecisionEvent, GenerationReferenceSelection
from bebcare.models.generation_run import GenerationRun
from bebcare.models.user import User
from bebcare.services.auth_dependency import get_current_admin_user
from bebcare.services.quality_diversity_events import compact_admin_timeline, expanded_admin_timeline

router = APIRouter(prefix="/admin/generation-runs", tags=["admin-generation"])


@router.get("")
def list_generation_runs(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
    owner_user_id: str | None = None,
    product_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = db.query(GenerationRun)
    if owner_user_id:
        query = query.filter(GenerationRun.owner_user_id == owner_user_id)
    if product_id:
        query = query.filter(GenerationRun.product_id == product_id)
    total = query.count()
    rows = (
        query.order_by(GenerationRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "run_id": run.run_id,
                "owner_user_id": run.owner_user_id,
                "product_id": run.product_id,
                "source": run.source,
                "status": run.status,
                "requested_selector_strategy": run.requested_selector_strategy,
                "executed_selector_strategy": run.executed_selector_strategy,
                "selection_seed": run.selection_seed,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in rows
        ],
    }


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
        .filter(GenerationReferenceSelection.generation_run_id == run_id)
        .first()
    )
    events = (
        db.query(GenerationDecisionEvent)
        .filter(GenerationDecisionEvent.generation_run_id == run_id)
        .order_by(GenerationDecisionEvent.sequence_number.asc())
        .all()
    )
    if expanded:
        return expanded_admin_timeline(run, events, selection)
    return compact_admin_timeline(run, events, selection)
