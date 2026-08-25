"""Onboarding checklist completion and one-time reward."""

from __future__ import annotations

from sqlalchemy.orm import Session

from bebcare.models.brand import Brand
from bebcare.models.generate_task import GenerateTask
from bebcare.models.image_credit import ImageCreditGrant
from bebcare.models.product import Product
from bebcare.models.task import ManualTaskDraft
from bebcare.services.credit_grant_service import (
    ONBOARDING_REWARD_CREDITS,
    SOURCE_ONBOARDING_REWARD,
    CreditError,
    create_grant,
    remaining_credits,
)


def has_non_generic_brand(db: Session, user_id: str) -> bool:
    return (
        db.query(Brand.brand_id)
        .filter(
            Brand.owner_user_id == user_id,
            Brand.is_generic.is_(False),
        )
        .first()
        is not None
    )


def has_product(db: Session, user_id: str) -> bool:
    return (
        db.query(Product.product_id)
        .filter(Product.owner_user_id == user_id)
        .first()
        is not None
    )


def has_generated_content(db: Session, user_id: str) -> bool:
    if (
        db.query(GenerateTask.task_id)
        .filter(
            GenerateTask.owner_user_id == user_id,
            GenerateTask.status == "SUCCESS",
        )
        .first()
        is not None
    ):
        return True
    return (
        db.query(ManualTaskDraft.draft_id)
        .filter(ManualTaskDraft.owner_user_id == user_id)
        .first()
        is not None
    )


def is_checklist_complete(db: Session, user_id: str) -> bool:
    return (
        has_non_generic_brand(db, user_id)
        and has_product(db, user_id)
        and has_generated_content(db, user_id)
    )


def onboarding_reward_claimed(db: Session, user_id: str) -> bool:
    return (
        db.query(ImageCreditGrant.id)
        .filter(
            ImageCreditGrant.user_id == user_id,
            ImageCreditGrant.source == SOURCE_ONBOARDING_REWARD,
        )
        .first()
        is not None
    )


def claim_onboarding_reward(db: Session, user_id: str) -> tuple[int, int]:
    """Grant onboarding credits once. Returns (newly_granted, remaining_total)."""
    if not is_checklist_complete(db, user_id):
        raise CreditError("incomplete", "Onboarding checklist is not complete")

    existing = (
        db.query(ImageCreditGrant)
        .filter(
            ImageCreditGrant.user_id == user_id,
            ImageCreditGrant.source == SOURCE_ONBOARDING_REWARD,
        )
        .first()
    )
    if existing:
        return 0, remaining_credits(db, user_id)

    create_grant(
        db,
        user_id=user_id,
        quantity=ONBOARDING_REWARD_CREDITS,
        source=SOURCE_ONBOARDING_REWARD,
        note="Onboarding checklist completion",
    )
    db.flush()
    return ONBOARDING_REWARD_CREDITS, remaining_credits(db, user_id)
