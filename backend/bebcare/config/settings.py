from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_SQLITE_URL = f"sqlite:///{os.path.join(_BACKEND_DIR, 'bebcare.db')}"


class Settings(BaseSettings):
    # development | production（本地默认 development + SQLite；上线改 production + Supabase）
    app_env: str = "development"

    # 本地默认 SQLite；生产请设为 Supabase Postgres 连接串
    database_url: str = _DEFAULT_SQLITE_URL

    # DeepSeek API配置（百炼云 OpenAI 兼容；base 如 …/v1，调用时会补全 /chat/completions）
    deepseek_api_key: str
    deepseek_api_url: str = (
        "https://ws-lxvmitlmy9ln8pda.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    )
    deepseek_model: str = "deepseek-v4-pro-0813"

    # 图像 Prompt 多模态（可选；开关在任务/预览侧，默认走纯文本 DeepSeek）
    # 未单独配置 VISION_API_KEY 时复用 DEEPSEEK_API_KEY；默认走 Agnes OpenAI 兼容接口
    vision_api_key: str | None = None
    vision_api_url: str | None = "https://api.agnes-ai.cn/v1"
    vision_model: str = "agnes-2.5-flash"
    # Agnes 图像生成（默认同 VISION_API_KEY / VISION_API_URL）
    vision_image_api_url: str | None = None
    vision_image_model: str = "agnes-image-2.1-flash"

    # Doubao API配置
    doubao_api_key: str
    doubao_api_url: str = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    doubao_model_id: str = "ep-20260616164806-7pj5g"

    # Buffer API配置
    buffer_api_token: str

    # GitHub图床配置
    github_token: str
    github_username: str
    github_repo: str
    github_branch: str = "main"

    # 安全配置
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # 管理员账户配置（可选）
    admin_username: str = "admin"
    admin_email: str = "admin@bebcare.com"
    admin_password: str | None = None

    # 是否允许公开注册（自托管可关闭）
    allow_public_signup: bool = True

    # 平台出图次数：注册试用张数；预扣超时（分钟）后可回收
    image_credit_signup_trial: int = 2
    image_credit_reserve_ttl_minutes: int = 15
    # Stripe 购买的 grant 有效天数；定时清零任务间隔（分钟）
    image_credit_stripe_expiry_days: int = 30
    image_credit_expire_interval_minutes: int = 60
    # 用户「升级订阅」联系方式（邮箱或 https 链接）；空则仅展示说明文案
    billing_contact: str | None = None

    # Stripe（测试/正式密钥；空则关闭在线购买）
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    # JSON 数组：[{"price_id":"price_xxx","credits":30,"label":"Basic — 30 credits","price_display":"$3.99"}]
    stripe_credit_packs: str = "[]"
    # Checkout success/cancel 回跳根 URL
    frontend_base_url: str = "http://localhost:5174"

    # 应用配置
    app_host: str = "0.0.0.0"
    app_port: int = 8888

    # 日志配置
    log_level: str = "INFO"

    # 启动时自动执行 alembic upgrade head（本地建议 true；多实例生产可改为 false，改由部署流水线执行）
    auto_migrate: bool = True

    # 调度与并发（HF Space 建议保持较小：workers=2, concurrent_jobs=1）
    scheduler_max_workers: int = 5
    scheduler_max_instances: int = 1
    scheduler_misfire_grace_seconds: int = 600
    max_concurrent_jobs: int = 5
    job_queue_wait_seconds: int = 120

    # Supabase / Postgres 连接池（对比模式并行轮询宜略大；单 HF 实例）
    db_pool_size: int = 16
    db_max_overflow: int = 16

    # CLIP/Torch 图文向量（默认关闭；启用需安装 requirements-clip.txt）
    enable_clip: bool = False

    # 启动时额外导入 baby_family 视觉预设（Bebcare 生产部署设为 true）
    seed_baby_dimensions: bool = False

    # CORS：白名单来自 ALLOWED_ORIGINS；禁止 * + credentials
    allowed_origins: str = "http://localhost:5174,http://127.0.0.1:5174"

    # 自动发布通知邮件（Resend；未配置 RESEND_API_KEY/RESEND_FROM 时跳过发送）
    resend_api_key: str | None = None
    resend_from: str | None = None

    # Phase 1A grounded reference selection. Default off preserves current random
    # scene-first behavior. Recommended first enablement: studio.
    # off | studio | manual_automation | all
    grounded_rollout_mode: str = "off"
    # 64-bit pHash bit Hamming distance; near-duplicates are excluded as supporting refs.
    phash_near_duplicate_hamming: int = 8

    # Phase 2B semantic asset intelligence. Default off: no vision analysis calls.
    # off | studio | all
    asset_intelligence_mode: str = "off"
    # Phase 3A deterministic quality protection. Default off: no new blocking.
    # off | studio | manual_automation | all
    quality_protection_mode: str = "off"

    model_config = SettingsConfigDict(
        env_file=os.path.join(_BACKEND_DIR, ".env"),
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not value:
            return _DEFAULT_SQLITE_URL
        # Supabase / Heroku 常见 postgres://，SQLAlchemy 需要 postgresql://
        if isinstance(value, str) and value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://"):]
        return value

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        if not value:
            return "development"
        return str(value).strip().lower()

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def normalize_allowed_origins(cls, value) -> str:
        if value is None:
            return "http://localhost:5174,http://127.0.0.1:5174"
        if isinstance(value, list):
            return ",".join(str(v).strip() for v in value if str(v).strip())
        return str(value)

    @field_validator("grounded_rollout_mode", mode="before")
    @classmethod
    def normalize_grounded_rollout_mode(cls, value: str) -> str:
        allowed = {"off", "studio", "manual_automation", "all"}
        mode = str(value or "off").strip().lower()
        if mode not in allowed:
            return "off"
        return mode

    @field_validator("asset_intelligence_mode", mode="before")
    @classmethod
    def normalize_asset_intelligence_mode(cls, value: str) -> str:
        allowed = {"off", "studio", "all"}
        mode = str(value or "off").strip().lower()
        if mode not in allowed:
            return "off"
        return mode

    @field_validator("quality_protection_mode", mode="before")
    @classmethod
    def normalize_quality_protection_mode(cls, value: str) -> str:
        allowed = {"off", "studio", "manual_automation", "all"}
        mode = str(value or "off").strip().lower()
        if mode not in allowed:
            return "off"
        return mode

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        # 拒绝通配符：与 allow_credentials 不兼容且不安全
        return [o for o in origins if o != "*"]

    @property
    def is_production(self) -> bool:
        return self.app_env in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return not self.is_production

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()
