import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model_name: str = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model_name: str = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    proxy_url: str = os.getenv("PROXY_URL", "")
    app_db_path: str = os.getenv("APP_DB_PATH", "data/math_gen.db")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-change-me")
    jwt_exp_minutes: int = int(os.getenv("JWT_EXP_MINUTES", "1440"))


settings = Settings()


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少必要环境变量: {name}")
    return value
