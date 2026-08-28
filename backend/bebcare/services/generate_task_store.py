from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from bebcare.database import SessionLocal
from bebcare.models.generate_task import GenerateTask

TASK_TTL = timedelta(hours=48)
STALE_IN_FLIGHT = timedelta(minutes=15)
_IN_FLIGHT = frozenset({"PENDING", "PROGRESS"})
ORPHANED_TASK_ERROR = "任务因服务中断已取消，请重新生成"


def _purge_expired(db: Session) -> None:
    cutoff = datetime.utcnow() - TASK_TTL
    db.query(GenerateTask).filter(GenerateTask.created_at < cutoff).delete(
        synchronize_session=False
    )


def create_generate_task(
    task_id: str, status: str = "PENDING", *, owner_user_id: str
) -> None:
    db = SessionLocal()
    try:
        _purge_expired(db)
        db.add(
            GenerateTask(
                task_id=task_id,
                status=status,
                result=None,
                owner_user_id=owner_user_id,
                workspace_id=None,
            )
        )
        db.commit()
    finally:
        db.close()


def fail_orphaned_generate_tasks() -> int:
    """Mark in-flight tasks as failed after process restart (BackgroundTasks do not resume)."""
    from bebcare.services.credit_grant_service import refund_reservation

    db = SessionLocal()
    try:
        rows = (
            db.query(GenerateTask)
            .filter(GenerateTask.status.in_(_IN_FLIGHT))
            .all()
        )
        if not rows:
            return 0
        for row in rows:
            row.status = "FAILURE"
            row.progress = 0
            row.stage = None
            row.result = {"error": ORPHANED_TASK_ERROR}
            row.updated_at = datetime.utcnow()
            refund_reservation(db, row.task_id)
        db.commit()
        return len(rows)
    finally:
        db.close()


def _maybe_fail_stale_task(db: Session, row: GenerateTask) -> None:
    if row.status not in _IN_FLIGHT:
        return
    ref = row.updated_at or row.created_at
    if not ref or ref >= datetime.utcnow() - STALE_IN_FLIGHT:
        return
    from bebcare.services.credit_grant_service import refund_reservation

    row.status = "FAILURE"
    row.progress = 0
    row.stage = None
    row.result = {"error": ORPHANED_TASK_ERROR}
    row.updated_at = datetime.utcnow()
    refund_reservation(db, row.task_id)
    db.commit()


def update_generate_task(
    task_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    stage: Optional[str] = None,
    result: Any = None,
    set_result: bool = False,
) -> None:
    from bebcare.services.credit_grant_service import (
        confirm_reservation,
        refund_reservation,
    )

    db = SessionLocal()
    try:
        row = db.query(GenerateTask).filter(GenerateTask.task_id == task_id).first()
        if not row:
            return
        if status is not None:
            row.status = status
        if progress is not None:
            row.progress = max(0, min(100, int(progress)))
        if stage is not None:
            row.stage = stage
        if set_result:
            row.result = result
        row.updated_at = datetime.utcnow()

        if status == "SUCCESS":
            confirm_reservation(db, task_id)
        elif status in ("FAILURE", "FAILED", "CANCELLED"):
            refund_reservation(db, task_id)

        db.commit()
    finally:
        db.close()


def get_generate_task(
    task_id: str,
    *,
    owner_user_id: str,
    db: Session | None = None,
) -> Optional[dict]:
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        row = (
            db.query(GenerateTask)
            .filter(
                GenerateTask.task_id == task_id,
                GenerateTask.owner_user_id == owner_user_id,
            )
            .first()
        )
        if not row:
            return None
        _maybe_fail_stale_task(db, row)
        return {
            "task_id": row.task_id,
            "status": row.status,
            "progress": row.progress,
            "stage": row.stage,
            "result": row.result,
        }
    finally:
        if own_session:
            db.close()
