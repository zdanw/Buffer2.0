"""Image credit grants: create, FEFO reserve, confirm/refund, trial, reclaim, expiry."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from bebcare.config.settings import settings
from bebcare.models.generate_task import GenerateTask
from bebcare.models.image_credit import ImageCreditGrant, ImageCreditReservation

SOURCE_SIGNUP_TRIAL = "signup_trial"
SOURCE_ADMIN_GRANT = "admin_grant"
SOURCE_STRIPE = "stripe"
SOURCE_ONBOARDING_REWARD = "onboarding_reward"

ONBOARDING_REWARD_CREDITS = 15

STATUS_ACTIVE = "active"
STATUS_EXHAUSTED = "exhausted"
STATUS_REVOKED = "revoked"
STATUS_EXPIRED = "expired"

RES_RESERVED = "reserved"
RES_CONFIRMED = "confirmed"
RES_REFUNDED = "refunded"

_IN_FLIGHT_TASK = frozenset({"PENDING", "PROGRESS"})


class CreditError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


def _unexpired_clause(now: Optional[datetime] = None):
    cutoff = now or datetime.utcnow()
    return or_(
        ImageCreditGrant.expires_at.is_(None),
        ImageCreditGrant.expires_at > cutoff,
    )


def remaining_credits(db: Session, user_id: str) -> int:
    total = (
        db.query(func.coalesce(func.sum(ImageCreditGrant.remaining), 0))
        .filter(
            ImageCreditGrant.user_id == user_id,
            ImageCreditGrant.status == STATUS_ACTIVE,
            _unexpired_clause(),
        )
        .scalar()
    )
    return int(total or 0)


def create_grant(
    db: Session,
    *,
    user_id: str,
    quantity: int,
    source: str,
    note: Optional[str] = None,
    external_ref: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> ImageCreditGrant:
    if quantity < 1:
        raise CreditError("invalid", "quantity must be >= 1")
    grant = ImageCreditGrant(
        id=str(uuid.uuid4()),
        user_id=user_id,
        source=source,
        quantity=quantity,
        remaining=quantity,
        status=STATUS_ACTIVE,
        note=note,
        external_ref=external_ref,
        expires_at=expires_at,
    )
    db.add(grant)
    db.flush()
    return grant


def ensure_signup_trial(db: Session, user_id: str) -> Optional[ImageCreditGrant]:
    existing = (
        db.query(ImageCreditGrant)
        .filter(
            ImageCreditGrant.user_id == user_id,
            ImageCreditGrant.source == SOURCE_SIGNUP_TRIAL,
        )
        .first()
    )
    if existing:
        return existing
    qty = max(0, int(settings.image_credit_signup_trial))
    if qty < 1:
        return None
    return create_grant(
        db, user_id=user_id, quantity=qty, source=SOURCE_SIGNUP_TRIAL
    )


def reserve_one(
    db: Session, *, user_id: str, generate_task_id: str
) -> ImageCreditReservation:
    existing = (
        db.query(ImageCreditReservation)
        .filter(ImageCreditReservation.generate_task_id == generate_task_id)
        .first()
    )
    if existing:
        if existing.status == RES_RESERVED:
            return existing
        raise CreditError("invalid", "reservation already finalized for task")

    # FEFO: earliest expires_at first; NULL (never expires) last; then created_at
    q = (
        db.query(ImageCreditGrant)
        .filter(
            ImageCreditGrant.user_id == user_id,
            ImageCreditGrant.status == STATUS_ACTIVE,
            ImageCreditGrant.remaining > 0,
            _unexpired_clause(),
        )
        .order_by(
            case((ImageCreditGrant.expires_at.is_(None), 1), else_=0).asc(),
            ImageCreditGrant.expires_at.asc(),
            ImageCreditGrant.created_at.asc(),
        )
    )
    # Postgres: row lock; SQLite ignores FOR UPDATE.
    try:
        grants = q.with_for_update().all()
    except Exception:
        grants = q.all()

    if not grants:
        raise CreditError("insufficient", "no image credits remaining")

    grant = grants[0]
    grant.remaining -= 1
    if grant.remaining <= 0:
        grant.remaining = 0
        grant.status = STATUS_EXHAUSTED
    grant.updated_at = datetime.utcnow()

    res = ImageCreditReservation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        generate_task_id=generate_task_id,
        grant_id=grant.id,
        amount=1,
        status=RES_RESERVED,
    )
    db.add(res)
    db.flush()
    return res


def expire_due_grants(db: Session) -> int:
    """Zero remaining and mark expired for due active grants. Idempotent."""
    now = datetime.utcnow()
    rows = (
        db.query(ImageCreditGrant)
        .filter(
            ImageCreditGrant.status == STATUS_ACTIVE,
            ImageCreditGrant.expires_at.isnot(None),
            ImageCreditGrant.expires_at <= now,
        )
        .all()
    )
    count = 0
    for grant in rows:
        grant.remaining = 0
        grant.status = STATUS_EXPIRED
        grant.updated_at = now
        count += 1
    if count:
        db.flush()
    return count


def confirm_reservation(db: Session, generate_task_id: str) -> None:
    res = (
        db.query(ImageCreditReservation)
        .filter(ImageCreditReservation.generate_task_id == generate_task_id)
        .first()
    )
    if not res:
        return
    if res.status != RES_RESERVED:
        return
    res.status = RES_CONFIRMED
    res.updated_at = datetime.utcnow()
    db.flush()


def refund_reservation(db: Session, generate_task_id: str) -> None:
    res = (
        db.query(ImageCreditReservation)
        .filter(ImageCreditReservation.generate_task_id == generate_task_id)
        .first()
    )
    if not res:
        return
    if res.status != RES_RESERVED:
        return

    try:
        grant = (
            db.query(ImageCreditGrant)
            .filter(ImageCreditGrant.id == res.grant_id)
            .with_for_update()
            .first()
        )
    except Exception:
        grant = (
            db.query(ImageCreditGrant).filter(ImageCreditGrant.id == res.grant_id).first()
        )

    if grant and grant.status not in (STATUS_REVOKED, STATUS_EXPIRED):
        grant.remaining += res.amount
        if grant.status == STATUS_EXHAUSTED:
            grant.status = STATUS_ACTIVE
        grant.updated_at = datetime.utcnow()

    res.status = RES_REFUNDED
    res.updated_at = datetime.utcnow()
    db.flush()


def revoke_grant(db: Session, grant_id: str) -> ImageCreditGrant:
    grant = db.query(ImageCreditGrant).filter(ImageCreditGrant.id == grant_id).first()
    if not grant:
        raise CreditError("not_found", "grant not found")
    grant.remaining = 0
    grant.status = STATUS_REVOKED
    grant.updated_at = datetime.utcnow()
    db.flush()
    return grant


def reclaim_stale_reservations(
    db: Session, *, older_than_minutes: Optional[int] = None
) -> int:
    ttl = older_than_minutes
    if ttl is None:
        ttl = int(settings.image_credit_reserve_ttl_minutes)
    cutoff = datetime.utcnow() - timedelta(minutes=ttl)
    rows = (
        db.query(ImageCreditReservation)
        .filter(
            ImageCreditReservation.status == RES_RESERVED,
            ImageCreditReservation.created_at < cutoff,
        )
        .all()
    )
    count = 0
    for res in rows:
        task = (
            db.query(GenerateTask)
            .filter(GenerateTask.task_id == res.generate_task_id)
            .first()
        )
        if task is not None and task.status in _IN_FLIGHT_TASK:
            continue
        refund_reservation(db, res.generate_task_id)
        count += 1
    return count
