from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./bebcare.db"
    redis_url: str = "redis://localhost:6379/0"
    
    deepseek_api_key: str = ""
    deepseek_api_url: str = "https://api.deepseek.com/v1"
    
    doubao_api_key: str = ""
    doubao_api_url: str = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    doubao_model_id: str = "ep-20260616164806-7pj5g"
    
    buffer_api_token: str = ""
    
    github_token: str = ""
    github_username: str = ""
    github_repo: str = ""
    github_branch: str = "main"
    
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    admin_username: str = "admin"
    admin_email: str = "admin@bebcare.com"
    admin_password: str | None = None
    
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()