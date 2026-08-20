"""Admin CRUD for platform (system) image providers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from bebcare.database import get_db
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.models.user import User
from bebcare.schemas.image_provider import (
    ImageProviderCreate,
    ImageProviderUpdate,
    ImageProviderResponse,
    ImageModelsResponse,
    ImageModelInfo,
    ImageProviderTestResponse,
    _normalize_manual_models,
)
from bebcare.utils.crypto import encrypt_secret, decrypt_secret, mask_secret
from bebcare.providers.registry import list_models_for_config, build_provider_from_config
from bebcare.services.auth_dependency import get_current_admin_user

router = APIRouter(
    prefix="/admin/system-image-providers", tags=["system-image-providers"]
)


def _to_response(config: ImageProviderConfig) -> ImageProviderResponse:
    try:
        plain = decrypt_secret(config.api_key_encrypted)
        masked = mask_secret(plain)
    except Exception:
        masked = "****"
    manual = _normalize_manual_models(
        config.manual_models if isinstance(config.manual_models, list) else []
    )
    return ImageProviderResponse(
        id=config.id,
        name=config.name,
        provider_type=config.provider_type,
        base_url=config.base_url,
        api_key_masked=masked,
        supports_list_models=bool(config.supports_list_models),
        default_model=config.default_model,
        manual_models=manual,
        extra_headers=config.extra_headers,
        extra_params=config.extra_params,
        is_active=bool(config.is_active),
        is_default=bool(config.is_default),
        is_system=bool(config.is_system),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _system_query(db: Session):
    return db.query(ImageProviderConfig).filter(
        ImageProviderConfig.is_system == True  # noqa: E712
    )


def _get_system_or_404(db: Session, provider_id: str) -> ImageProviderConfig:
    row = _system_query(db).filter(ImageProviderConfig.id == provider_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


def _clear_other_system_defaults(db: Session, keep_id: str | None = None):
    q = _system_query(db).filter(ImageProviderConfig.is_default == True)  # noqa: E712
    if keep_id:
        q = q.filter(ImageProviderConfig.id != keep_id)
    for row in q.all():
        row.is_default = False


@router.get("/", response_model=List[ImageProviderResponse])
def list_system_providers(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    rows = _system_query(db).order_by(ImageProviderConfig.created_at.desc()).all()
    return [_to_response(r) for r in rows]


@router.post("/", response_model=ImageProviderResponse, status_code=201)
def create_system_provider(
    body: ImageProviderCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    if body.is_default:
        _clear_other_system_defaults(db)
    row = ImageProviderConfig(
        id=str(uuid.uuid4()),
        owner_user_id=None,
        name=body.name,
        provider_type=body.provider_type,
        base_url=body.base_url.rstrip("/"),
        api_key_encrypted=encrypt_secret(body.api_key),
        supports_list_models=body.supports_list_models,
        default_model=body.default_model,
        manual_models=[m.model_dump() for m in (body.manual_models or [])],
        extra_headers=body.extra_headers,
        extra_params=body.extra_params,
        is_active=body.is_active,
        is_default=body.is_default,
        is_system=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.put("/{provider_id}", response_model=ImageProviderResponse)
def update_system_provider(
    provider_id: str,
    body: ImageProviderUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    row = _get_system_or_404(db, provider_id)
    data = body.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    if api_key:
        row.api_key_encrypted = encrypt_secret(api_key)
    if data.get("is_default") is True:
        _clear_other_system_defaults(db, keep_id=provider_id)
    for key, value in data.items():
        if key == "base_url" and isinstance(value, str):
            value = value.rstrip("/")
        if key == "manual_models" and isinstance(value, list):
            value = [
                m if isinstance(m, dict) else {"id": str(m), "description": None}
                for m in value
            ]
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/{provider_id}", status_code=204)
def delete_system_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    row = _get_system_or_404(db, provider_id)
    db.delete(row)
    db.commit()
    return None


@router.post("/{provider_id}/set-default", response_model=ImageProviderResponse)
def set_system_default(
    provider_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    row = _get_system_or_404(db, provider_id)
    _clear_other_system_defaults(db, keep_id=provider_id)
    row.is_default = True
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.get("/{provider_id}/models", response_model=ImageModelsResponse)
def get_system_provider_models(
    provider_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    row = _get_system_or_404(db, provider_id)
    merged: list[ImageModelInfo] = []
    seen: set[str] = set()
    for entry in _normalize_manual_models(
        row.manual_models if isinstance(row.manual_models, list) else []
    ):
        if entry.id in seen:
            continue
        seen.add(entry.id)
        merged.append(
            ImageModelInfo(id=entry.id, description=entry.description, source="manual")
        )
    remote_msg = None
    if row.supports_list_models:
        try:
            remote = list_models_for_config(row)
            for m in remote:
                mid = m.get("id")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                merged.append(
                    ImageModelInfo(id=mid, owned_by=m.get("owned_by"), source="remote")
                )
        except Exception:
            if not merged:
                remote_msg = "拉取远程模型失败，请使用手动模型列表"
    return ImageModelsResponse(
        models=merged, message=remote_msg, allow_manual_input=True
    )


@router.post("/{provider_id}/test", response_model=ImageProviderTestResponse)
def test_system_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    row = _get_system_or_404(db, provider_id)
    try:
        provider = build_provider_from_config(row)
        verify = getattr(provider, "verify_credentials", None)
        if callable(verify):
            verify()
        return ImageProviderTestResponse(ok=True, message="连接成功")
    except Exception as e:
        return ImageProviderTestResponse(ok=False, message=str(e))
