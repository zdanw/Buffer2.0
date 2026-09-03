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
    ImageProviderDiscoverRequest,
    ImageProviderDiscoverResponse,
    ImageSizeCapabilitiesResponse,
    resolve_configured_model_id,
)
from bebcare.utils.crypto import encrypt_secret, decrypt_secret, mask_secret
from bebcare.utils.user_errors import user_safe_detail
from bebcare.providers.registry import (
    list_models_for_config,
    build_provider_from_config,
    discover_models_for_credentials,
    resolve_provider_preset,
    SYSTEM_IMAGE_PROVIDER_ID,
)
from bebcare.providers.size_catalog import get_size_capabilities
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.services.ownership import get_owned_or_404, owned_query, stamp_owner
from bebcare.models.user import User
from pydantic import BaseModel
from typing import List, Optional, Any
import uuid

router = APIRouter(prefix="/image-providers", tags=["image-providers"])


class SystemProviderSummary(BaseModel):
    has_provider: bool
    id: Optional[str] = None
    name: Optional[str] = None
    provider_type: Optional[str] = None
    default_model: Optional[str] = None
    manual_models: List[Any] = []


def _to_response(config: ImageProviderConfig) -> ImageProviderResponse:
    try:
        plain = decrypt_secret(config.api_key_encrypted)
        masked = mask_secret(plain)
    except Exception:
        masked = "****"
    manual = []
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
        is_system=bool(getattr(config, "is_system", False)),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _clear_other_defaults(db: Session, owner_user_id: str, keep_id: str | None = None):
    q = (
        db.query(ImageProviderConfig)
        .filter(ImageProviderConfig.is_default == True)  # noqa: E712
        .filter(ImageProviderConfig.owner_user_id == owner_user_id)
    )
    if keep_id:
        q = q.filter(ImageProviderConfig.id != keep_id)
    for row in q.all():
        row.is_default = False


@router.get("/", response_model=List[ImageProviderResponse])
def list_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (
        owned_query(db, ImageProviderConfig, current_user)
        .filter(ImageProviderConfig.is_system == False)  # noqa: E712
        .order_by(ImageProviderConfig.created_at.desc())
        .all()
    )
    return [_to_response(r) for r in rows]


@router.get("/system/summary", response_model=SystemProviderSummary)
def system_provider_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Public (authenticated) summary of the platform image provider — no API key."""
    row = (
        db.query(ImageProviderConfig)
        .filter(
            ImageProviderConfig.is_system == True,  # noqa: E712
            ImageProviderConfig.is_active == True,  # noqa: E712
            ImageProviderConfig.is_default == True,  # noqa: E712
        )
        .first()
    )
    if row is None:
        row = (
            db.query(ImageProviderConfig)
            .filter(
                ImageProviderConfig.is_system == True,  # noqa: E712
                ImageProviderConfig.is_active == True,  # noqa: E712
            )
            .order_by(ImageProviderConfig.updated_at.desc())
            .first()
        )
    if row is None:
        return SystemProviderSummary(has_provider=False)
    manual = []
    return SystemProviderSummary(
        has_provider=True,
        id=row.id,
        name=row.name,
        provider_type=row.provider_type,
        default_model=row.default_model,
        manual_models=[],
    )


@router.get("/capabilities", response_model=ImageSizeCapabilitiesResponse)
def get_provider_capabilities(
    provider_id: Optional[str] = None,
    model: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    provider_type = None
    if provider_id == SYSTEM_IMAGE_PROVIDER_ID:
        raise HTTPException(status_code=404, detail="Not found")
    if provider_id:
        row = get_owned_or_404(
            db, ImageProviderConfig, provider_id, current_user, id_attr="id"
        )
        provider_type = row.provider_type
    else:
        default = (
            owned_query(db, ImageProviderConfig, current_user)
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


@router.post("/discover", response_model=ImageProviderDiscoverResponse)
def discover_provider_models(
    body: ImageProviderDiscoverRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Validate API key and list models before saving a provider."""
    del current_user  # auth gate only
    try:
        resolved_url, resolved_list = resolve_provider_preset(
            body.provider_type,
            body.base_url,
            body.supports_list_models,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=user_safe_detail(e, fallback="Invalid image provider configuration"),
        ) from e

    ok, raw_models, message = discover_models_for_credentials(
        provider_type=body.provider_type,
        api_key=body.api_key,
        base_url=resolved_url,
        supports_list_models=resolved_list,
    )
    models = [
        ImageModelInfo(
            id=str(m.get("id") or ""),
            description=m.get("description"),
            owned_by=m.get("owned_by"),
            source="remote",
        )
        for m in raw_models
        if m.get("id")
    ]
    return ImageProviderDiscoverResponse(
        ok=ok,
        models=models,
        message=message,
        base_url=resolved_url,
        supports_list_models=resolved_list,
    )


@router.post("/", response_model=ImageProviderResponse, status_code=201)
def create_provider(
    body: ImageProviderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if body.is_default:
        _clear_other_defaults(db, current_user.user_id)
    try:
        base_url, supports_list_models = resolve_provider_preset(
            body.provider_type,
            body.base_url,
            body.supports_list_models,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=user_safe_detail(e, fallback="Invalid image provider configuration"),
        ) from e
    row = ImageProviderConfig(
        id=str(uuid.uuid4()),
        name=body.name,
        provider_type=body.provider_type,
        base_url=base_url,
        api_key_encrypted=encrypt_secret(body.api_key),
        supports_list_models=supports_list_models,
        default_model=body.default_model,
        manual_models=[],
        extra_headers=body.extra_headers,
        extra_params=body.extra_params,
        is_active=body.is_active,
        is_default=body.is_default,
        is_system=False,
    )
    stamp_owner(row, current_user)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.put("/{provider_id}", response_model=ImageProviderResponse)
def update_provider(
    provider_id: str,
    body: ImageProviderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = get_owned_or_404(
        db, ImageProviderConfig, provider_id, current_user, id_attr="id"
    )

    data = body.model_dump(exclude_unset=True)
    data.pop("manual_models", None)
    api_key = data.pop("api_key", None)
    if api_key:
        row.api_key_encrypted = encrypt_secret(api_key)

    if data.get("is_default") is True:
        _clear_other_defaults(db, current_user.user_id, keep_id=provider_id)

    provider_type = data.get("provider_type", row.provider_type)
    if "base_url" in data or "provider_type" in data or "supports_list_models" in data:
        try:
            base_url, supports_list_models = resolve_provider_preset(
                provider_type,
                data.get("base_url", row.base_url),
                data.get("supports_list_models", row.supports_list_models),
            )
        except ValueError as e:
            raise HTTPException(
            status_code=400,
            detail=user_safe_detail(e, fallback="Invalid image provider configuration"),
        ) from e
        data["base_url"] = base_url
        data["supports_list_models"] = supports_list_models

    for key, value in data.items():
        if key == "base_url" and isinstance(value, str):
            value = value.rstrip("/")
        if key == "manual_models":
            continue
        setattr(row, key, value)

    row.manual_models = []

    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/{provider_id}", status_code=204)
def delete_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = get_owned_or_404(
        db, ImageProviderConfig, provider_id, current_user, id_attr="id"
    )
    db.delete(row)
    db.commit()
    return None


@router.get("/{provider_id}/models", response_model=ImageModelsResponse)
def get_provider_models(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = get_owned_or_404(
        db, ImageProviderConfig, provider_id, current_user, id_attr="id"
    )

    model_id = resolve_configured_model_id(row.default_model, row.manual_models)
    models: list[ImageModelInfo] = []
    if model_id:
        models.append(ImageModelInfo(id=model_id, source="configured"))

    return ImageModelsResponse(
        models=models,
        message=None if models else "未配置模型，请在 Provider 设置中选择模型",
        allow_manual_input=False,
    )


@router.post("/{provider_id}/test", response_model=ImageProviderTestResponse)
def test_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    row = get_owned_or_404(
        db, ImageProviderConfig, provider_id, current_user, id_attr="id"
    )

    try:
        provider = build_provider_from_config(row)
        verify = getattr(provider, "verify_credentials", None)
        if callable(verify):
            verify()

        if row.supports_list_models:
            models = provider.list_models()
            if models:
                msg = f"连接成功，拉取到 {len(models)} 个模型"
            elif callable(verify):
                msg = "连接成功（鉴权通过，模型列表为空，可手填 Model ID）"
            else:
                msg = "连接成功（模型列表为空，可手填 Model ID）"
            return ImageProviderTestResponse(ok=True, message=msg)
        if callable(verify):
            return ImageProviderTestResponse(ok=True, message="连接成功（鉴权通过）")
        if not row.default_model:
            return ImageProviderTestResponse(ok=True, message="配置有效（未启用列表拉取，请确认 default_model）")
        return ImageProviderTestResponse(ok=True, message="配置有效")
    except Exception as e:
        return ImageProviderTestResponse(ok=False, message=str(e))
