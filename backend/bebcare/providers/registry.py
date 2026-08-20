from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from bebcare.config.settings import settings
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.utils.crypto import decrypt_secret
from bebcare.providers.openai_compatible import OpenAICompatibleImageProvider
from bebcare.providers.doubao_ark import DoubaoArkImageProvider
from bebcare.providers.aliyun_maas import AliyunMaasMultimodalProvider
from bebcare.providers.google_gemini import GoogleGeminiImageProvider

# Virtual provider id for legacy env Doubao (not stored in DB)
SYSTEM_IMAGE_PROVIDER_ID = "system"

_NO_PROVIDER_MSG = "未配置图像供应商。请到设置页添加你自己的图像供应商后再生成。"
SYSTEM_PROVIDER_UNAVAILABLE_MSG = "平台图像供应商未配置，请联系管理员。"


def _build_provider(config: ImageProviderConfig, api_key: str):
    kwargs = dict(
        api_key=api_key,
        base_url=config.base_url,
        default_model=config.default_model,
        extra_headers=config.extra_headers or {},
        extra_params=config.extra_params or {},
        supports_list_models=bool(config.supports_list_models),
    )
    if config.provider_type == "doubao_ark":
        return DoubaoArkImageProvider(**kwargs)
    if config.provider_type == "openai_compatible":
        return OpenAICompatibleImageProvider(**kwargs)
    if config.provider_type == "aliyun_maas":
        return AliyunMaasMultimodalProvider(**kwargs)
    if config.provider_type == "google_gemini":
        return GoogleGeminiImageProvider(**kwargs)
    raise ValueError(f"Unsupported provider_type: {config.provider_type}")


def _env_fallback_provider():
    return DoubaoArkImageProvider(
        api_key=settings.doubao_api_key,
        base_url=settings.doubao_api_url,
        default_model=settings.doubao_model_id,
        supports_list_models=False,
    )


def resolve_system_image_provider(
    db: Session,
    image_model: Optional[str] = None,
) -> Tuple[object, Optional[str]]:
    """Resolve the active system (platform) image provider. No owner filter."""
    config = (
        db.query(ImageProviderConfig)
        .filter(
            ImageProviderConfig.is_system == True,  # noqa: E712
            ImageProviderConfig.is_active == True,  # noqa: E712
            ImageProviderConfig.is_default == True,  # noqa: E712
        )
        .first()
    )
    if config is None:
        config = (
            db.query(ImageProviderConfig)
            .filter(
                ImageProviderConfig.is_system == True,  # noqa: E712
                ImageProviderConfig.is_active == True,  # noqa: E712
            )
            .order_by(ImageProviderConfig.updated_at.desc())
            .first()
        )
    if config is None:
        raise ValueError(SYSTEM_PROVIDER_UNAVAILABLE_MSG)

    api_key = decrypt_secret(config.api_key_encrypted)
    provider = _build_provider(config, api_key)
    resolved_model = image_model or config.default_model
    return provider, resolved_model


def resolve_image_provider(
    db: Optional[Session] = None,
    image_provider_id: Optional[str] = None,
    image_model: Optional[str] = None,
    *,
    owner_user_id: Optional[str] = None,
) -> Tuple[object, Optional[str]]:
    """
    Resolve provider + model id for one owner.
    No env / platform-key fallback. Missing owner_user_id or no usable
    config raises ValueError (API maps to 400).
    """
    if not owner_user_id:
        raise ValueError("owner_user_id is required to resolve an image provider")

    if image_provider_id == SYSTEM_IMAGE_PROVIDER_ID:
        raise ValueError(_NO_PROVIDER_MSG)

    config: Optional[ImageProviderConfig] = None

    if db is not None and image_provider_id:
        config = (
            db.query(ImageProviderConfig)
            .filter(
                ImageProviderConfig.id == image_provider_id,
                ImageProviderConfig.owner_user_id == owner_user_id,
                ImageProviderConfig.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not config:
            raise ValueError(_NO_PROVIDER_MSG)

    if config is None and db is not None:
        config = (
            db.query(ImageProviderConfig)
            .filter(
                ImageProviderConfig.owner_user_id == owner_user_id,
                ImageProviderConfig.is_active == True,  # noqa: E712
                ImageProviderConfig.is_default == True,  # noqa: E712
            )
            .first()
        )

    if config is None:
        raise ValueError(_NO_PROVIDER_MSG)

    api_key = decrypt_secret(config.api_key_encrypted)
    provider = _build_provider(config, api_key)
    resolved_model = image_model or config.default_model
    return provider, resolved_model


def list_models_for_config(config: ImageProviderConfig) -> List[dict]:
    api_key = decrypt_secret(config.api_key_encrypted)
    provider = _build_provider(config, api_key)
    return provider.list_models()


def build_provider_from_config(config: ImageProviderConfig):
    api_key = decrypt_secret(config.api_key_encrypted)
    return _build_provider(config, api_key)
