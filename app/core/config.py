from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Math SaaS"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/aimath"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"
    jwt_exp_minutes: int = 1440

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model_name: str = "gpt-4o-mini"
    ocr_timeout_seconds: int = 45
    gaokao_enable_llm: bool = True
    gaokao_default_provider: str = "glm"
    gaokao_default_model: str = ""
    gaokao_glm_api_key: str = ""
    gaokao_glm_base_url: str = ""
    gaokao_glm_default_model: str = ""
    gaokao_openai_api_key: str = ""
    gaokao_openai_base_url: str = "https://api.openai.com/v1"
    gaokao_openai_default_model: str = "gpt-4o-mini"

    wechat_appid: str = ""
    wechat_secret: str = ""

    oss_provider: str = "aliyun"
    oss_endpoint: str = ""
    oss_bucket: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_public_base_url: str = ""
    oss_upload_expire_seconds: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
