"""Resolve which Buffer API token to use for a product/brand publish."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from bebcare.models.brand import Brand
from bebcare.models.buffer_account import BufferAccount
from bebcare.models.product import Product
from bebcare.utils.crypto import decrypt_secret


class BufferAccountUnavailable(Exception):
    """Brand is bound to a Buffer account that cannot be used."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def resolve_buffer_api_token(
    db: Session,
    *,
    product_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    owner_user_id: str,
) -> Optional[str]:
    """
    Preference (always scoped to owner_user_id):
    1. Brand-bound Buffer account (via product → brand or explicit brand_id)
       — bound account must belong to the same owner; if bound but
       inactive/missing, do NOT fall through to another account
    2. Active default Buffer account for this owner
    3. None (no env BUFFER_API_TOKEN fallback)
    """
    resolved_brand_id = brand_id
    if not resolved_brand_id and product_id:
        product = (
            db.query(Product)
            .filter(
                Product.product_id == str(product_id),
                Product.owner_user_id == owner_user_id,
            )
            .first()
        )
        if product and product.brand_id:
            resolved_brand_id = str(product.brand_id)

    if resolved_brand_id:
        brand = (
            db.query(Brand)
            .filter(
                Brand.brand_id == str(resolved_brand_id),
                Brand.owner_user_id == owner_user_id,
            )
            .first()
        )
        if brand and brand.buffer_account_id:
            account = (
                db.query(BufferAccount)
                .filter(BufferAccount.id == brand.buffer_account_id)
                .first()
            )
            if not account or account.owner_user_id != owner_user_id:
                raise BufferAccountUnavailable(
                    f"Brand '{brand.name}' is bound to a missing Buffer account"
                )
            if not account.is_active:
                raise BufferAccountUnavailable(
                    f"Brand '{brand.name}' is bound to disabled Buffer account '{account.name}'"
                )
            return decrypt_secret(account.api_token_encrypted)

    default = (
        db.query(BufferAccount)
        .filter(
            BufferAccount.owner_user_id == owner_user_id,
            BufferAccount.is_default == True,  # noqa: E712
            BufferAccount.is_active == True,  # noqa: E712
        )
        .first()
    )
    if default:
        return decrypt_secret(default.api_token_encrypted)

    return None
