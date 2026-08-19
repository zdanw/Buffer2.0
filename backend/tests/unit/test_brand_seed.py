"""Legacy brand assignment must not steal other users' products."""

from bebcare.database import SessionLocal
from bebcare.models import BEBCARE_BRAND_ID, Product
from bebcare.models.user import User
from bebcare.services.brand_seed_service import assign_legacy_products_to_bebcare


def test_assign_legacy_only_touches_admin_owned_products(client):
    db = SessionLocal()
    try:
        admin = (
            db.query(User)
            .filter(User.is_admin.is_(True))
            .order_by(User.created_at.asc())
            .first()
        )
        assert admin is not None

        other = User(
            username="legacy_other_user",
            email="legacy_other_user@test.local",
            hashed_password="x",
            is_admin=False,
        )
        db.add(other)
        db.flush()

        admin_prod = Product(
            product_id="legacy-admin-nl",
            product_name="Admin Night Light",
            category="Night Lights",
            owner_user_id=admin.user_id,
            brand_id=None,
        )
        other_prod = Product(
            product_id="legacy-other-nl",
            product_name="Other Night Light",
            category="Night Lights",
            owner_user_id=other.user_id,
            brand_id=None,
        )
        db.add_all([admin_prod, other_prod])
        db.commit()

        assign_legacy_products_to_bebcare(db)

        db.refresh(admin_prod)
        db.refresh(other_prod)
        assert admin_prod.brand_id == BEBCARE_BRAND_ID
        assert other_prod.brand_id is None
    finally:
        db.close()
