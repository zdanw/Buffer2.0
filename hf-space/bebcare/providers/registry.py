from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from bebcare.config.settings import settings
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.utils.crypto import decrypt_secret
from bebcare.providers.openai_compatible import OpenAICompatibleImageProvider
from bebcare.providers.doubao_ark import DoubaoArkImageProvider
from bebcare.providers.aliyun_maas import AliyunMaasMultimodalProvider

# Virtual provider id for env Doubao / Seedream (not stored in DB)
SYSTEM_IMAGE_PROVIDER_ID = "system"


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
    raise ValueError(f"Unsupported provider_type: {config.provider_type}")


def _env_fallback_provider():
    return DoubaoArkImageProvider(
        api_key=settings.doubao_api_key,
        base_url=settings.doubao_api_url,
        default_model=settings.doubao_model_id,
        supports_list_models=False,
    )


def resolve_image_provider(
    db: Optional[Session] = None,
    image_provider_id: Optional[str] = None,
    image_model: Optional[str] = None,
) -> Tuple[object, Optional[str]]:
    """
    Resolve provider + model id.
    Order: explicit provider id → DB default → .env Doubao (Seedream).
    Returns (provider_instance, resolved_model_or_None).
    """
    if image_provider_id == SYSTEM_IMAGE_PROVIDER_ID:
        provider = _env_fallback_provider()
        return provider, image_model or settings.doubao_model_id

    config: Optional[ImageProviderConfig] = None

    if db is not None and image_provider_id:
        config = (
            db.query(ImageProviderConfig)
            .filter(
                ImageProviderConfig.id == image_provider_id,
                ImageProviderConfig.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not config:
            raise ValueError(f"Image provider not found or inactive: {image_provider_id}")

    if config is None and db is not None:
        config = (
            db.query(ImageProviderConfig)
            .filter(
                ImageProviderConfig.is_active == True,  # noqa: E712
                ImageProviderConfig.is_default == True,  # noqa: E712
            )
            .first()
        )

    if config is None:
        provider = _env_fallback_provider()
        return provider, image_model or settings.doubao_model_id

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
