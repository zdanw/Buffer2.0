from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from bebcare.database import get_db
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.schemas.image_provider import (
    ImageProviderCreate,
    ImageProviderUpdate,
    ImageProviderResponse,
    ImageModelsResponse,
    ImageModelInfo,
    ImageProviderTestResponse,
    ImageSizeCapabilitiesResponse,
    ManualModelEntry,
    _normalize_manual_models,
)
from bebcare.utils.crypto import encrypt_secret, decrypt_secret, mask_secret
from bebcare.providers.registry import (
    list_models_for_config,
    build_provider_from_config,
    SYSTEM_IMAGE_PROVIDER_ID,
    _env_fallback_provider,
)
from bebcare.providers.size_catalog import get_size_capabilities
from bebcare.config.settings import settings
from bebcare.services.auth_dependency import get_current_admin_user, get_current_active_user
from bebcare.models.user import User
import uuid

router = APIRouter(prefix="/image-providers", tags=["image-providers"])


def _system_provider_response() -> ImageProviderResponse:
    """Env Doubao / Seedream fallback, shown as a read-only system default."""
    model_id = (settings.doubao_model_id or "").strip() or None
    manual: list[ManualModelEntry] = []
    if model_id:
        manual.append(
            ManualModelEntry(
                id=model_id,
                description="System default (env DOUBAO_*)",
            )
        )
    try:
        masked = mask_secret(settings.doubao_api_key or "")
    except Exception:
        masked = "****"
    return ImageProviderResponse(
        id=SYSTEM_IMAGE_PROVIDER_ID,
        name="Seedream",
        provider_type="doubao_ark",
        base_url=(settings.doubao_api_url or "").rstrip("/"),
        api_key_masked=masked,
        supports_list_models=False,
        default_model=model_id,
        manual_models=manual,
        is_active=True,
        is_default=False,
        is_system=True,
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
        is_system=False,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _clear_other_defaults(db: Session, keep_id: str | None = None):
    q = db.query(ImageProviderConfig).filter(ImageProviderConfig.is_default == True)  # noqa: E712
    if keep_id:
        q = q.filter(ImageProviderConfig.id != keep_id)
    for row in q.all():
        row.is_default = False


@router.get("/", response_model=List[ImageProviderResponse])
def list_providers(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    rows = db.query(ImageProviderConfig).order_by(ImageProviderConfig.created_at.desc()).all()
    return [_system_provider_response()] + [_to_response(r) for r in rows]


@router.get("/capabilities", response_model=ImageSizeCapabilitiesResponse)
def get_provider_capabilities(
    provider_id: Optional[str] = None,
    model: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    provider_type = None
    if provider_id == SYSTEM_IMAGE_PROVIDER_ID:
        provider_type = "doubao_ark"
    elif provider_id:
        row = db.query(ImageProviderConfig).filter(ImageProviderConfig.id == provider_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Provider not found")
        provider_type = row.provider_type
    else:
        default = (
            db.query(ImageProviderConfig)
            .filter(ImageProviderConfig.is_default == True)  # noqa: E712
            .filter(ImageProviderConfig.is_active == True)  # noqa: E712
            .first()
        )
        provider_type = default.provider_type if default else "doubao_ark"

    caps = get_size_capabilities(provider_type, model)
    return ImageSizeCapabilitiesResponse(
        supported_sizes=caps["supported_sizes"],
        default_size=caps["default_size"],
        provider_type=provider_type,
        allow_custom=bool(caps.get("allow_custom", True)),
    )


@router.post("/", response_model=ImageProviderResponse, status_code=201)
def create_provider(
    body: ImageProviderCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    if body.is_default:
        _clear_other_defaults(db)
    row = ImageProviderConfig(
        id=str(uuid.uuid4()),
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
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.put("/{provider_id}", response_model=ImageProviderResponse)
def update_provider(
    provider_id: str,
    body: ImageProviderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    if provider_id == SYSTEM_IMAGE_PROVIDER_ID:
        raise HTTPException(status_code=400, detail="System default provider is read-only")
    row = db.query(ImageProviderConfig).filter(ImageProviderConfig.id == provider_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Provider not found")

    data = body.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    if api_key:
        row.api_key_encrypted = encrypt_secret(api_key)

    if data.get("is_default") is True:
        _clear_other_defaults(db, keep_id=provider_id)

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
def delete_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    if provider_id == SYSTEM_IMAGE_PROVIDER_ID:
        raise HTTPException(status_code=400, detail="System default provider cannot be deleted")
    row = db.query(ImageProviderConfig).filter(ImageProviderConfig.id == provider_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(row)
    db.commit()
    return None


@router.get("/{provider_id}/models", response_model=ImageModelsResponse)
def get_provider_models(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    if provider_id == SYSTEM_IMAGE_PROVIDER_ID:
        model_id = (settings.doubao_model_id or "").strip()
        models = (
            [
                ImageModelInfo(
                    id=model_id,
                    description="System default (env DOUBAO_*)",
                    source="manual",
                )
            ]
            if model_id
            else []
        )
        return ImageModelsResponse(models=models, message=None, allow_manual_input=True)

    row = db.query(ImageProviderConfig).filter(ImageProviderConfig.id == provider_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Provider not found")

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
            if not remote and not merged:
                remote_msg = "未能从厂商拉取模型列表，请在 Provider 中维护手动模型列表"
        except Exception:
            if not merged:
                remote_msg = "拉取远程模型失败，请使用手动模型列表或手填 Model ID"
    elif not merged:
        remote_msg = "未启用远程拉取且无手动模型，请添加手动模型列表或手填 Model ID"

    return ImageModelsResponse(
        models=merged,
        message=remote_msg,
        allow_manual_input=True,
    )


@router.post("/{provider_id}/test", response_model=ImageProviderTestResponse)
def test_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    if provider_id == SYSTEM_IMAGE_PROVIDER_ID:
        try:
            _env_fallback_provider()
            model = (settings.doubao_model_id or "").strip()
            msg = (
                f"系统默认 Seedream 配置有效（模型: {model}）"
                if model
                else "系统默认 Seedream 配置有效（未设置 DOUBAO_MODEL_ID）"
            )
            return ImageProviderTestResponse(ok=True, message=msg)
        except Exception as e:
            return ImageProviderTestResponse(ok=False, message=str(e))

    row = db.query(ImageProviderConfig).filter(ImageProviderConfig.id == provider_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Provider not found")

    try:
        provider = build_provider_from_config(row)
        if row.supports_list_models:
            models = provider.list_models()
            return ImageProviderTestResponse(
                ok=True,
                message=f"连接成功，拉取到 {len(models)} 个模型" if models else "连接成功（模型列表为空，可手填 Model ID）",
            )
        # No list endpoint — just verify key decrypt + provider construct
        if not row.default_model:
            return ImageProviderTestResponse(ok=True, message="配置有效（未启用列表拉取，请确认 default_model）")
        return ImageProviderTestResponse(ok=True, message="配置有效")
    except Exception as e:
        return ImageProviderTestResponse(ok=False, message=str(e))
