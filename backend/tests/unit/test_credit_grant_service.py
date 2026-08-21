import uuid
from datetime import datetime, timedelta

import pytest
from bebcare.database import Base, SessionLocal, engine
from bebcare.models.user import User
from bebcare.models.generate_task import GenerateTask
from bebcare.services.credit_grant_service import (
    create_grant,
    remaining_credits,
    reserve_one,
    confirm_reservation,
    refund_reservation,
    ensure_signup_trial,
    expire_due_grants,
    CreditError,
    STATUS_EXPIRED,
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
    db_session.flush()
    return uid


@pytest.fixture()
def generate_task_id(db_session, user_id):
    tid = str(uuid.uuid4())
    db_session.add(
        GenerateTask(
            task_id=tid,
            status="PENDING",
            owner_user_id=user_id,
            workspace_id=None,
        )
    )
    db_session.flush()
    return tid


def test_create_and_remaining(db_session, user_id):
    create_grant(db_session, user_id=user_id, quantity=5, source="admin_grant")
    db_session.commit()
    assert remaining_credits(db_session, user_id) == 5


def test_reserve_confirm(db_session, user_id, generate_task_id):
    create_grant(db_session, user_id=user_id, quantity=1, source="admin_grant")
    db_session.flush()
    reserve_one(db_session, user_id=user_id, generate_task_id=generate_task_id)
    db_session.flush()
    assert remaining_credits(db_session, user_id) == 0
    confirm_reservation(db_session, generate_task_id)
    db_session.flush()
    assert remaining_credits(db_session, user_id) == 0


def test_reserve_refund_restores(db_session, user_id, generate_task_id):
    create_grant(db_session, user_id=user_id, quantity=1, source="admin_grant")
    db_session.flush()
    reserve_one(db_session, user_id=user_id, generate_task_id=generate_task_id)
    db_session.flush()
    refund_reservation(db_session, generate_task_id)
    db_session.flush()
    assert remaining_credits(db_session, user_id) == 1


def test_reserve_insufficient(db_session, user_id, generate_task_id):
    with pytest.raises(CreditError) as ei:
        reserve_one(db_session, user_id=user_id, generate_task_id=generate_task_id)
    assert ei.value.code == "insufficient"


def test_signup_trial_idempotent(db_session, user_id, monkeypatch):
    from bebcare.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "image_credit_signup_trial", 2)
    ensure_signup_trial(db_session, user_id)
    db_session.flush()
    ensure_signup_trial(db_session, user_id)
    db_session.flush()
    assert remaining_credits(db_session, user_id) == 2


def test_double_reserve_last_credit(db_session, user_id):
    create_grant(db_session, user_id=user_id, quantity=1, source="admin_grant")
    db_session.flush()
    tid1 = str(uuid.uuid4())
    tid2 = str(uuid.uuid4())
    for tid in (tid1, tid2):
        db_session.add(
            GenerateTask(
                task_id=tid,
                status="PENDING",
                owner_user_id=user_id,
                workspace_id=None,
            )
        )
    db_session.flush()
    reserve_one(db_session, user_id=user_id, generate_task_id=tid1)
    db_session.flush()
    with pytest.raises(CreditError) as ei:
        reserve_one(db_session, user_id=user_id, generate_task_id=tid2)
    assert ei.value.code == "insufficient"


def test_expired_grant_excluded_from_remaining(db_session, user_id):
    past = datetime.utcnow() - timedelta(days=1)
    create_grant(
        db_session, user_id=user_id, quantity=5, source="stripe", expires_at=past
    )
    db_session.flush()
    assert remaining_credits(db_session, user_id) == 0


def test_future_expiry_still_counts(db_session, user_id):
    future = datetime.utcnow() + timedelta(days=10)
    create_grant(
        db_session, user_id=user_id, quantity=4, source="stripe", expires_at=future
    )
    db_session.flush()
    assert remaining_credits(db_session, user_id) == 4


def test_reserve_fefo_uses_earlier_expiry(db_session, user_id):
    soon = datetime.utcnow() + timedelta(days=1)
    later = datetime.utcnow() + timedelta(days=10)
    create_grant(
        db_session, user_id=user_id, quantity=1, source="stripe", expires_at=later
    )
    g_soon = create_grant(
        db_session, user_id=user_id, quantity=1, source="stripe", expires_at=soon
    )
    db_session.flush()
    tid = str(uuid.uuid4())
    db_session.add(
        GenerateTask(
            task_id=tid, status="PENDING", owner_user_id=user_id, workspace_id=None
        )
    )
    db_session.flush()
    res = reserve_one(db_session, user_id=user_id, generate_task_id=tid)
    assert res.grant_id == g_soon.id


def test_expire_due_grants_zeros_and_marks(db_session, user_id):
    past = datetime.utcnow() - timedelta(hours=1)
    g = create_grant(
        db_session, user_id=user_id, quantity=3, source="stripe", expires_at=past
    )
    db_session.flush()
    n = expire_due_grants(db_session)
    db_session.flush()
    assert n == 1
    db_session.refresh(g)
    assert g.remaining == 0
    assert g.status == STATUS_EXPIRED
    assert expire_due_grants(db_session) == 0
