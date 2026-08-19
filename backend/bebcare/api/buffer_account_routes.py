from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from bebcare.database import get_db
from bebcare.models.buffer_account import BufferAccount
from bebcare.schemas.buffer_account import (
    BufferAccountCreate,
    BufferAccountUpdate,
    BufferAccountResponse,
    BufferAccountTestResponse,
    BufferBrandSummary,
)
from bebcare.utils.crypto import encrypt_secret, decrypt_secret, mask_secret
from bebcare.publisher.buffer_publisher import BufferGraphQLClient
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.services.ownership import get_owned_or_404, owned_query, stamp_owner
from bebcare.models.user import User
import uuid

router = APIRouter(prefix="/buffer-accounts", tags=["buffer-accounts"])


def _to_response(account: BufferAccount) -> BufferAccountResponse:
    try:
        plain = decrypt_secret(account.api_token_encrypted)
        masked = mask_secret(plain)
    except Exception:
        masked = "****"

    brands = list(account.brands or [])
    return BufferAccountResponse(
        id=account.id,
        name=account.name,
        api_token_masked=masked,
        buffer_email=account.buffer_email,
        buffer_remote_id=account.buffer_remote_id,
        brand_ids=[b.brand_id for b in brands],
        brands=[
            BufferBrandSummary(
                brand_id=b.brand_id,
                name=b.name,
                slug=b.slug,
                is_generic=bool(b.is_generic),
                is_system=bool(b.is_system),
            )
            for b in brands
        ],
        is_active=bool(account.is_active),
        is_default=bool(account.is_default),
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _clear_other_defaults(db: Session, owner_user_id: str, keep_id: str | None = None):
    q = (
        db.query(BufferAccount)
        .filter(BufferAccount.is_default == True)  # noqa: E712
        .filter(BufferAccount.owner_user_id == owner_user_id)
    )
    if keep_id:
        q = q.filter(BufferAccount.id != keep_id)
    for row in q.all():
        row.is_default = False


def _probe_token(api_token: str) -> dict:
    client = BufferGraphQLClient(api_token=api_token)
    account = client.fetch_account_info()
    if not account:
        detail = client.last_error or "Invalid Buffer token or API unreachable"
        raise HTTPException(status_code=400, detail=detail)
    return account


@router.get("/", response_model=List[BufferAccountResponse])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (
        owned_query(db, BufferAccount, current_user)
        .options(joinedload(BufferAccount.brands))
        .order_by(BufferAccount.created_at.desc())
        .all()
    )
    return [_to_response(r) for r in rows]


@router.post("/", response_model=BufferAccountResponse, status_code=201)
def create_account(
    body: BufferAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    remote = _probe_token(body.api_token.strip())
    if body.is_default:
        _clear_other_defaults(db, current_user.user_id)

    row = BufferAccount(
        id=str(uuid.uuid4()),
        name=body.name.strip(),
        api_token_encrypted=encrypt_secret(body.api_token.strip()),
        buffer_email=remote.get("email"),
        buffer_remote_id=remote.get("id"),
        is_active=body.is_active,
        is_default=body.is_default,
    )
    stamp_owner(row, current_user)
    db.add(row)
    db.commit()
    row = (
        owned_query(db, BufferAccount, current_user)
        .options(joinedload(BufferAccount.brands))
        .filter(BufferAccount.id == row.id)
        .first()
    )
    return _to_response(row)


@router.put("/{account_id}", response_model=BufferAccountResponse)
def update_account(
    account_id: str,
    body: BufferAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = get_owned_or_404(
        db, BufferAccount, account_id, current_user, id_attr="id"
    )

    data = body.model_dump(exclude_unset=True)
    api_token = data.pop("api_token", None)

    if api_token and str(api_token).strip():
        remote = _probe_token(str(api_token).strip())
        row.api_token_encrypted = encrypt_secret(str(api_token).strip())
        row.buffer_email = remote.get("email")
        row.buffer_remote_id = remote.get("id")

    if data.get("is_default") is True:
        _clear_other_defaults(db, current_user.user_id, keep_id=account_id)

    for key, value in data.items():
        if key == "name" and isinstance(value, str):
            value = value.strip()
        setattr(row, key, value)

    db.commit()
    row = (
        owned_query(db, BufferAccount, current_user)
        .options(joinedload(BufferAccount.brands))
        .filter(BufferAccount.id == account_id)
        .first()
    )
    return _to_response(row)


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = get_owned_or_404(
        db, BufferAccount, account_id, current_user, id_attr="id"
    )
    db.delete(row)
    db.commit()
    return None


@router.post("/{account_id}/test", response_model=BufferAccountTestResponse)
def test_account(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = get_owned_or_404(
        db, BufferAccount, account_id, current_user, id_attr="id"
    )

    try:
        token = decrypt_secret(row.api_token_encrypted)
        remote = _probe_token(token)
        email = remote.get("email")
        remote_id = remote.get("id")
        row.buffer_email = email
        row.buffer_remote_id = remote_id
        db.commit()
        orgs = remote.get("organizations") or []
        org_names = ", ".join(o.get("name") or o.get("id") or "?" for o in orgs[:3])
        suffix = f"；组织: {org_names}" if org_names else ""
        return BufferAccountTestResponse(
            ok=True,
            message=f"连接成功（{email or remote_id or 'ok'}）{suffix}",
            email=email,
            remote_id=remote_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        return BufferAccountTestResponse(ok=False, message=str(e))
