from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bebcare.database import get_db
from bebcare.models.user import User
from bebcare.models.image_credit import ImageCreditGrant
from bebcare.schemas.image_credit import (
    CreditGrantCreate,
    CreditGrantResponse,
    CreditGrantListResponse,
)
from bebcare.services.auth_dependency import get_current_admin_user
from bebcare.services.credit_grant_service import (
    SOURCE_ADMIN_GRANT,
    create_grant,
    remaining_credits,
    revoke_grant,
    CreditError,
)

router = APIRouter(prefix="/auth/users", tags=["credits"])


@router.get("/{user_id}/credit-grants", response_model=CreditGrantListResponse)
def list_user_credit_grants(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    grants = (
        db.query(ImageCreditGrant)
        .filter(ImageCreditGrant.user_id == user_id)
        .order_by(ImageCreditGrant.created_at.desc())
        .all()
    )
    return CreditGrantListResponse(
        remaining_total=remaining_credits(db, user_id),
        grants=grants,
    )


@router.post("/{user_id}/credit-grants", response_model=CreditGrantResponse)
def grant_user_credits(
    user_id: str,
    body: CreditGrantCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        grant = create_grant(
            db,
            user_id=user_id,
            quantity=body.quantity,
            source=SOURCE_ADMIN_GRANT,
            note=body.note,
        )
        db.commit()
        db.refresh(grant)
    except CreditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return grant


@router.post(
    "/{user_id}/credit-grants/{grant_id}/revoke",
    response_model=CreditGrantResponse,
)
def revoke_user_credit_grant(
    user_id: str,
    grant_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    grant = (
        db.query(ImageCreditGrant)
        .filter(ImageCreditGrant.id == grant_id, ImageCreditGrant.user_id == user_id)
        .first()
    )
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")
    try:
        revoked = revoke_grant(db, grant_id)
        db.commit()
        db.refresh(revoked)
    except CreditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return revoked
