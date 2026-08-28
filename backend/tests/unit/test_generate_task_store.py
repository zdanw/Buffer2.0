"""Tests for durable generate task store."""

import uuid
from datetime import datetime, timedelta

import pytest
from bebcare.database import Base, SessionLocal, engine
from bebcare.models.generate_task import GenerateTask
from bebcare.models.user import User
from bebcare.services.generate_task_store import (
    ORPHANED_TASK_ERROR,
    create_generate_task,
    fail_orphaned_generate_tasks,
    get_generate_task,
)
import bebcare.models  # noqa: F401


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


@pytest.fixture()
def user_id(db_session):
    uid = str(uuid.uuid4())
    db_session.add(
        User(
            user_id=uid,
            username=f"u_{uid[:8]}",
            email=f"{uid[:8]}@test.local",
            hashed_password="x",
            is_active=True,
            is_admin=False,
        )
    )
    db_session.commit()
    return uid


def test_fail_orphaned_generate_tasks_marks_in_flight_as_failure(user_id):
    create_generate_task("task-orphan-1", status="PROGRESS", owner_user_id=user_id)

    count = fail_orphaned_generate_tasks()
    assert count == 1

    task = get_generate_task("task-orphan-1", owner_user_id=user_id)
    assert task is not None
    assert task["status"] == "FAILURE"
    assert task["result"]["error"] == ORPHANED_TASK_ERROR


def test_get_generate_task_fails_stale_in_flight_task(db_session, user_id):
    create_generate_task("task-stale-1", status="PROGRESS", owner_user_id=user_id)

    row = db_session.query(GenerateTask).filter(GenerateTask.task_id == "task-stale-1").one()
    row.updated_at = datetime.utcnow() - timedelta(minutes=20)
    db_session.commit()

    task = get_generate_task("task-stale-1", owner_user_id=user_id)
    assert task is not None
    assert task["status"] == "FAILURE"
    assert task["result"]["error"] == ORPHANED_TASK_ERROR
