from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from bebcare.database import SessionLocal
from bebcare.models.generate_task import GenerateTask

TASK_TTL = timedelta(hours=48)


def _purge_expired(db: Session) -> None:
    cutoff = datetime.utcnow() - TASK_TTL
    db.query(GenerateTask).filter(GenerateTask.created_at < cutoff).delete(
        synchronize_session=False
    )


def create_generate_task(task_id: str, status: str = "PENDING") -> None:
    db = SessionLocal()
    try:
        _purge_expired(db)
        db.add(GenerateTask(task_id=task_id, status=status, result=None))
        db.commit()
    finally:
        db.close()


def update_generate_task(
    task_id: str,
    *,
    status: Optional[str] = None,
    result: Any = None,
    set_result: bool = False,
) -> None:
    db = SessionLocal()
    try:
        row = db.query(GenerateTask).filter(GenerateTask.task_id == task_id).first()
        if not row:
            return
        if status is not None:
            row.status = status
        if set_result:
            row.result = result
        row.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def get_generate_task(task_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        row = db.query(GenerateTask).filter(GenerateTask.task_id == task_id).first()
        if not row:
            return None
        return {
            "task_id": row.task_id,
            "status": row.status,
            "result": row.result,
        }
    finally:
        db.close()
