"""Seed isolated demo data for documentation screenshots (docs-demo user)."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from bebcare.database import SessionLocal
from bebcare.models import (
    Brand,
    BufferAccount,
    GenerateTask,
    ManualTaskDraft,
    Product,
    ProductImage,
    PromptDimension,
    ScheduledTask,
    TaskExecution,
    User,
)
from bebcare.models.image_credit import ImageCreditGrant
from bebcare.services.auth_service import get_password_hash
from bebcare.services.credit_grant_service import (
    ONBOARDING_REWARD_CREDITS,
    SOURCE_ONBOARDING_REWARD,
    create_grant,
)
from bebcare.utils.crypto import encrypt_secret

DOCS_DEMO_USERNAME = os.environ.get("DOCS_DEMO_USERNAME", "docs-demo")
DOCS_DEMO_EMAIL = os.environ.get("DOCS_DEMO_EMAIL", "docs-demo@pulseforge.local")
DOCS_DEMO_PASSWORD = os.environ.get("DOCS_DEMO_PASSWORD", "DocsDemo2026!")
DEMO_FRONTEND = os.environ.get("PULSEFORGE_FRONTEND_URL", "http://localhost:5174")

# Stable IDs so re-runs are idempotent
BRAND_ID = "d0c50000-0000-4000-8000-000000000001"
PRODUCT_LAMP_ID = "d0c50000-0000-4000-8000-000000000011"
PRODUCT_PILLOW_ID = "d0c50000-0000-4000-8000-000000000012"
PRODUCT_CANDLE_ID = "d0c50000-0000-4000-8000-000000000013"
BUFFER_ID = "d0c50000-0000-4000-8000-000000000021"
TASK_ID = "d0c50000-0000-4000-8000-000000000031"
DRAFT_ID = "d0c50000-0000-4000-8000-000000000041"
GEN_TASK_ID = "d0c50000-0000-4000-8000-000000000051"

PRODUCT_TYPE = "Home & Living"


def _demo_url(filename: str) -> str:
    return f"{DEMO_FRONTEND}/docs/demo/{filename}"


def _get_or_create_user(db: Session) -> User:
    user = db.query(User).filter(User.username == DOCS_DEMO_USERNAME).first()
    if user:
        return user
    user = User(
        user_id=str(uuid.uuid4()),
        username=DOCS_DEMO_USERNAME,
        email=DOCS_DEMO_EMAIL,
        hashed_password=get_password_hash(DOCS_DEMO_PASSWORD),
        is_active=True,
        is_admin=False,
        onboarding_completed_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()
    return user


def _purge_user_data(db: Session, user_id: str) -> None:
    db.query(ManualTaskDraft).filter(ManualTaskDraft.owner_user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(TaskExecution).filter(TaskExecution.owner_user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(ScheduledTask).filter(ScheduledTask.owner_user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(GenerateTask).filter(GenerateTask.owner_user_id == user_id).delete(
        synchronize_session=False
    )
    product_ids = [
        row[0]
        for row in db.query(Product.product_id).filter(Product.owner_user_id == user_id).all()
    ]
    if product_ids:
        db.query(ProductImage).filter(ProductImage.product_id.in_(product_ids)).delete(
            synchronize_session=False
        )
    db.query(Product).filter(Product.owner_user_id == user_id).delete(synchronize_session=False)
    db.query(Brand).filter(Brand.owner_user_id == user_id).delete(synchronize_session=False)
    db.query(PromptDimension).filter(PromptDimension.owner_user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(BufferAccount).filter(BufferAccount.owner_user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(ImageCreditGrant).filter(ImageCreditGrant.user_id == user_id).delete(
        synchronize_session=False
    )
    db.flush()


def _seed_brand(db: Session, user_id: str, buffer_id: str) -> Brand:
    brand = Brand(
        brand_id=BRAND_ID,
        slug="luma-home",
        name="Luma Home",
        is_generic=False,
        is_system=False,
        voice="Warm, modern, and approachable — like a friend who always has the coziest apartment.",
        audience="Design-conscious homeowners aged 28–45 who love calm, curated spaces.",
        tone_keywords="warm, minimal, inviting",
        default_hashtags=["#LumaHome", "#CozyLiving", "#HomeDecor"],
        emoji_style="moderate",
        words_to_avoid="cheap, discount, viral",
        logo_in_images="preserve",
        vertical_pack="general",
        default_product_type=PRODUCT_TYPE,
        buffer_account_id=buffer_id,
        owner_user_id=user_id,
    )
    db.add(brand)
    return brand


def _seed_products(db: Session, user_id: str, brand_id: str) -> list[Product]:
    catalog = [
        (
            PRODUCT_LAMP_ID,
            "Ceramic Table Lamp",
            "Soft-glow bedside lamp with a matte ceramic base and linen shade.",
            "lamp.png",
            "scene-living.png",
        ),
        (
            PRODUCT_PILLOW_ID,
            "Linen Throw Pillow",
            "Neutral linen cover with a plush insert — layers beautifully on sofas and beds.",
            "pillow.png",
            None,
        ),
        (
            PRODUCT_CANDLE_ID,
            "Scented Candle Set",
            "Three soy candles in amber glass — cedar, bergamot, and vanilla notes.",
            "candle.png",
            "scene-nursery.png",
        ),
    ]
    products: list[Product] = []
    for pid, name, desc, img, scene in catalog:
        product = Product(
            product_id=pid,
            product_name=name,
            brand_id=brand_id,
            category=PRODUCT_TYPE,
            description=desc,
            selling_points="Hand-finished materials, calm palette, gift-ready packaging",
            use_brand_voice=True,
            offering_type="physical_product",
            owner_user_id=user_id,
        )
        db.add(product)
        db.add(
            ProductImage(
                image_id=str(uuid.uuid4()),
                product_id=pid,
                cdn_url=_demo_url(img),
                image_type="product",
                is_preferred=True,
                sort_index=0,
                width=800,
                height=800,
            )
        )
        if scene:
            db.add(
                ProductImage(
                    image_id=str(uuid.uuid4()),
                    product_id=pid,
                    cdn_url=_demo_url(scene),
                    image_type="scene",
                    sort_index=1,
                    width=800,
                    height=800,
                )
            )
        products.append(product)
    return products


def _seed_visual_styles(db: Session, user_id: str) -> None:
    styles = [
        ("scenes", "morning-light", "Sunlit living room", "Soft morning light through sheer curtains"),
        ("scenes", "cozy-evening", "Cozy evening corner", "Warm lamp glow on a side table at dusk"),
        ("lighting", "golden-hour", "Golden hour", "Warm directional light with gentle shadows"),
        ("lighting", "soft-diffused", "Soft diffused", "Even, flattering light — no harsh highlights"),
        ("compositions", "rule-thirds", "Rule of thirds", "Product placed on the lower third with negative space"),
        ("styles", "minimal-modern", "Minimal modern", "Clean lines, muted palette, uncluttered surfaces"),
    ]
    for dim_type, item_id, name, name_en in styles:
        db.add(
            PromptDimension(
                dimension_id=str(uuid.uuid4()),
                product_type=PRODUCT_TYPE,
                dimension_type=dim_type,
                item_id=item_id,
                name=name,
                name_en=name_en,
                enabled=True,
                owner_user_id=user_id,
            )
        )


def _seed_buffer(db: Session, user_id: str) -> BufferAccount:
    account = BufferAccount(
        id=BUFFER_ID,
        name="Luma Home — Buffer",
        api_token_encrypted=encrypt_secret("docs-demo-buffer-token-not-real"),
        buffer_email="studio@luma-home.demo",
        is_active=True,
        is_default=True,
        owner_user_id=user_id,
    )
    db.add(account)
    return account


def _seed_automation(db: Session, user_id: str) -> ScheduledTask:
    task = ScheduledTask(
        task_id=TASK_ID,
        name="Weekday morning posts",
        cron="0 9 * * 1-5",
        mode="manual",
        target_products=[PRODUCT_LAMP_ID, PRODUCT_PILLOW_ID],
        platforms=["instagram", "facebook"],
        reference_image_count=2,
        run_count_per_execution=1,
        generate_image_count=2,
        generate_copy_count=2,
        enabled=True,
        use_scene_reference=True,
        use_vision_image_prompt=False,
        realistic_placement=True,
        notify_on_publish=False,
        owner_user_id=user_id,
    )
    db.add(task)
    return task


def _seed_review_draft(db: Session, user_id: str, task_id: str) -> None:
    db.add(
        ManualTaskDraft(
            draft_id=DRAFT_ID,
            task_id=task_id,
            product_id=PRODUCT_LAMP_ID,
            images=[
                _demo_url("lamp.png"),
                _demo_url("scene-living.png"),
            ],
            copywritings=[
                "Morning light, softer corners. Our ceramic table lamp brings a warm glow to every room. ✨ #LumaHome #CozyLiving",
                "Designed for calm evenings — matte ceramic, linen shade, and a glow that feels like home.",
            ],
            status="pending",
            owner_user_id=user_id,
        )
    )


def _seed_generate_task(db: Session, user_id: str) -> None:
    db.add(
        GenerateTask(
            task_id=GEN_TASK_ID,
            status="SUCCESS",
            progress=100,
            stage="done",
            result={"platform": "instagram"},
            owner_user_id=user_id,
        )
    )


def seed_docs_sandbox(db: Session | None = None) -> str:
    """Reset and seed docs-demo sandbox. Returns user_id."""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        user = _get_or_create_user(db)
        user.onboarding_completed_at = datetime.utcnow()
        user.is_admin = False
        _purge_user_data(db, user.user_id)
        buffer = _seed_buffer(db, user.user_id)
        db.flush()
        _seed_brand(db, user.user_id, buffer.id)
        db.flush()
        _seed_products(db, user.user_id, BRAND_ID)
        db.flush()
        _seed_visual_styles(db, user.user_id)
        db.flush()
        task = _seed_automation(db, user.user_id)
        db.flush()
        _seed_review_draft(db, user.user_id, task.task_id)
        _seed_generate_task(db, user.user_id)
        create_grant(
            db,
            user_id=user.user_id,
            quantity=ONBOARDING_REWARD_CREDITS,
            source=SOURCE_ONBOARDING_REWARD,
            note="Docs sandbox — onboarding reward pre-claimed for screenshots",
        )
        db.commit()
        return user.user_id
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()


def main() -> int:
    user_id = seed_docs_sandbox()
    print(f"Docs sandbox ready for user '{DOCS_DEMO_USERNAME}' ({user_id})")
    print(f"  Password: {DOCS_DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
