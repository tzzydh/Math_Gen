from fastapi import FastAPI

from core.settings import settings

app = FastAPI(title="Math Gen API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/config/check")
def config_check():
    return {
        "openai_base_url": settings.openai_base_url,
        "openai_model_name": settings.openai_model_name,
        "gemini_model_name": settings.gemini_model_name,
        "has_openai_key": bool(settings.openai_api_key),
        "has_gemini_key": bool(settings.gemini_api_key),
        "proxy_enabled": bool(settings.proxy_url),
    }
