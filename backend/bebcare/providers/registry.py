from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from bebcare.config.settings import settings
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.utils.crypto import decrypt_secret
from bebcare.providers.openai_compatible import OpenAICompatibleImageProvider
from bebcare.providers.doubao_ark import DoubaoArkImageProvider
from bebcare.providers.aliyun_maas import AliyunMaasMultimodalProvider
from bebcare.providers.google_gemini import GoogleGeminiImageProvider
from bebcare.providers.agnes import AgnesImageProvider

# Virtual provider id for legacy env Doubao (not stored in DB)
SYSTEM_IMAGE_PROVIDER_ID = "system"

_NO_PROVIDER_MSG = "未配置图像供应商。请到设置页添加你自己的图像供应商后再生成。"
SYSTEM_PROVIDER_UNAVAILABLE_MSG = "平台图像供应商未配置，请联系管理员。"

PROVIDER_TYPE_PRESETS: dict[str, dict] = {
    "openai_compatible": {
        "base_url": "https://api.openai.com/v1",
        "supports_list_models": True,
    },
    "doubao_ark": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "supports_list_models": True,
    },
    "aliyun_maas": {
        "base_url": (
            "https://ws-lxvmitlmy9ln8pda.cn-beijing.maas.aliyuncs.com/api/v1/"
            "services/aigc/multimodal-generation/generation"
        ),
        "supports_list_models": True,
    },
    "google_gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "supports_list_models": True,
    },
    "agnes": {
        "base_url": "https://api.agnes-ai.cn/v1",
        "supports_list_models": True,
    },
}


@dataclass
class _EphemeralProviderConfig:
    provider_type: str
    base_url: str
    default_model: Optional[str] = None
    extra_headers: dict = field(default_factory=dict)
    extra_params: dict = field(default_factory=dict)
    supports_list_models: bool = True


def resolve_provider_preset(
    provider_type: str,
    base_url: Optional[str] = None,
    supports_list_models: Optional[bool] = None,
) -> tuple[str, bool]:
    preset = PROVIDER_TYPE_PRESETS.get(provider_type, {})
    resolved_url = (base_url or preset.get("base_url") or "").rstrip("/")
    if not resolved_url:
        raise ValueError(f"Unknown provider_type or missing base_url: {provider_type}")
    resolved_list = (
        supports_list_models
        if supports_list_models is not None
        else bool(preset.get("supports_list_models", True))
    )
    return resolved_url, resolved_list


def discover_models_for_credentials(
    provider_type: str,
    api_key: str,
    base_url: Optional[str] = None,
    supports_list_models: Optional[bool] = None,
) -> tuple[bool, List[dict], Optional[str]]:
    """Probe credentials and list models without persisting a provider row."""
    resolved_url, resolved_list = resolve_provider_preset(
        provider_type, base_url, supports_list_models
    )
    config = _EphemeralProviderConfig(
        provider_type=provider_type,
        base_url=resolved_url,
        supports_list_models=resolved_list,
    )
    try:
        provider = _build_provider(config, api_key)  # type: ignore[arg-type]
        verify = getattr(provider, "verify_credentials", None)
        if callable(verify):
            verify()
        models: List[dict] = []
        if resolved_list:
            models = provider.list_models() or []
        if models:
            return True, models, None
        if callable(verify):
            return True, [], "连接成功，未找到图像模型，请手动填写 Model ID"
        return True, [], "未找到图像模型，请手动填写 Model ID"
    except Exception as e:
        return False, [], str(e)


def _build_provider(config: ImageProviderConfig | _EphemeralProviderConfig, api_key: str):
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
    if config.provider_type == "agnes":
        return AgnesImageProvider(**kwargs)
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
