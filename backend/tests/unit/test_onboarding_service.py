import uuid

import pytest
from bebcare.database import Base, SessionLocal, engine
from bebcare.models.brand import Brand
from bebcare.models.generate_task import GenerateTask
from bebcare.models.product import Product
from bebcare.models.user import User
from bebcare.services.credit_grant_service import remaining_credits
from bebcare.services.onboarding_service import (
    claim_onboarding_reward,
    is_checklist_complete,
    onboarding_reward_claimed,
)
from bebcare.services.credit_grant_service import CreditError
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


def _seed_checklist(db_session, user_id: str):
    brand = Brand(
        brand_id=str(uuid.uuid4()),
        slug="acme",
        name="Acme",
        is_generic=False,
        owner_user_id=user_id,
        workspace_id=None,
    )
    db_session.add(brand)
    db_session.add(
        Product(
            product_id=str(uuid.uuid4()),
            product_name="Widget",
            category="General",
            brand_id=brand.brand_id,
            owner_user_id=user_id,
            workspace_id=None,
        )
    )
    db_session.add(
        GenerateTask(
            task_id=str(uuid.uuid4()),
            status="SUCCESS",
            owner_user_id=user_id,
            workspace_id=None,
        )
    )
    db_session.flush()


def test_onboarding_reward_granted_once(db_session, user_id):
    _seed_checklist(db_session, user_id)
    assert is_checklist_complete(db_session, user_id) is True

    granted, remaining = claim_onboarding_reward(db_session, user_id)
    db_session.commit()
    assert granted == 15
    assert remaining == 15
    assert onboarding_reward_claimed(db_session, user_id) is True

    granted2, remaining2 = claim_onboarding_reward(db_session, user_id)
    db_session.commit()
    assert granted2 == 0
    assert remaining2 == 15
    assert remaining_credits(db_session, user_id) == 15


def test_onboarding_reward_requires_checklist(db_session, user_id):
    with pytest.raises(CreditError) as exc:
        claim_onboarding_reward(db_session, user_id)
    assert exc.value.code == "incomplete"
