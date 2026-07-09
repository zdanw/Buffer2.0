from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 数据库配置
    database_url: str = "sqlite:///./bebcare.db"
    redis_url: str = "redis://localhost:6379/0"
    
    # DeepSeek API配置
    deepseek_api_key: str
    deepseek_api_url: str = "https://api.deepseek.com/v1"
    
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
    access_token_expire_minutes: int = 30
    
    # 管理员账户配置（可选）
    admin_username: str = "admin"
    admin_email: str = "admin@bebcare.com"
    admin_password: str | None = None
    
    # 应用配置
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    
    # 日志配置
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()