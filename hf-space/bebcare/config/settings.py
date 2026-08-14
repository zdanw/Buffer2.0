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
    deepseek_model: str = "deepseek-v4-pro"

    # 图像 Prompt 多模态（可选；开关在任务/预览侧，默认走纯文本 DeepSeek）
    # 未单独配置时复用 DEEPSEEK_* 的 key/url；模型须为支持视觉的百炼兼容模型（如 qwen-vl-max）
    vision_api_key: str | None = None
    vision_api_url: str | None = None
    vision_model: str = "qwen3.5-omni-plus-2026-03-15"

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

    # 应用配置
    app_host: str = "0.0.0.0"
    app_port: int = 8080

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

    # Supabase / Postgres 连接池（免费档连接有限；配合短生命周期 Session）
    db_pool_size: int = 8
    db_max_overflow: int = 8

    # CLIP/Torch 图文向量（默认关闭；启用需安装 requirements-clip.txt）
    enable_clip: bool = False

    # 启动时额外导入 baby_family 视觉预设（Bebcare 生产部署设为 true）
    seed_baby_dimensions: bool = False

    # CORS：白名单来自 ALLOWED_ORIGINS；禁止 * + credentials
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

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
            return "http://localhost:5173,http://127.0.0.1:5173"
        if isinstance(value, list):
            return ",".join(str(v).strip() for v in value if str(v).strip())
        return str(value)

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
