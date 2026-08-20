"""Resolve which Buffer API token to use for a product/brand publish."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from bebcare.models.brand import Brand
from bebcare.models.buffer_account import BufferAccount
from bebcare.models.product import Product
from bebcare.utils.crypto import decrypt_secret


class BufferAccountUnavailable(Exception):
    """Brand has no usable Buffer account binding."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


_UNBOUND_MSG = (
    "品牌「{name}」尚未绑定 Buffer 账户，请到「品牌管理」中为该品牌绑定后再发布。"
)


def resolve_buffer_api_token(
    db: Session,
    *,
    product_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    owner_user_id: str,
) -> Optional[str]:
    """
    Resolve Buffer token for one owner (no global-default / env fallback):
    1. Brand-bound Buffer account (via product → brand or explicit brand_id)
       — bound account must belong to the same owner; if bound but
       inactive/missing, raise (do not fall through)
    2. Brand exists but unbound → raise with bind reminder
    3. No brand resolved → None (caller maps to 400)
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

    if not resolved_brand_id:
        return None

    brand = (
        db.query(Brand)
        .filter(
            Brand.brand_id == str(resolved_brand_id),
            Brand.owner_user_id == owner_user_id,
        )
        .first()
    )
    if not brand:
        return None

    if not brand.buffer_account_id:
        raise BufferAccountUnavailable(_UNBOUND_MSG.format(name=brand.name))

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
