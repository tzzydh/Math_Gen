import json

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from core.auth import create_token, verify_token
from core.settings import settings
from core.db import (
    init_db,
    create_org,
    list_orgs,
    create_user,
    list_users,
    verify_user,
    create_question,
    list_questions,
)

app = FastAPI(title="Math Gen API", version="0.3.0")
init_db()


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.3.0"}


@app.get("/config/check")
def config_check():
    return {
        "openai_base_url": settings.openai_base_url,
        "openai_model_name": settings.openai_model_name,
        "gemini_model_name": settings.gemini_model_name,
        "has_openai_key": bool(settings.openai_api_key),
        "has_gemini_key": bool(settings.gemini_api_key),
        "proxy_enabled": bool(settings.proxy_url),
        "db_path": settings.app_db_path,
        "admin_token_enabled": bool(settings.admin_token),
        "jwt_exp_minutes": settings.jwt_exp_minutes,
    }


def verify_admin_token(x_admin_token: str | None):
    if not settings.admin_token:
        return
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


def get_current_user(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization[7:]
    try:
        return verify_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


class OrgCreateReq(BaseModel):
    name: str
    plan: str = "free"
    status: str = "active"


class UserCreateReq(BaseModel):
    org_id: int
    role: str
    name: str
    email: str = ""
    password: str = "123456"


class LoginReq(BaseModel):
    org_id: int
    name: str
    password: str


class QuestionCreateReq(BaseModel):
    stem: str
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    analysis: str = ""
    difficulty: str = "中"
    chapter: str = ""


class PaperGenerateReq(BaseModel):
    chapter: str | None = None
    difficulty: str | None = None
    num_questions: int = 10


@app.post("/v0/auth/login")
def api_login(payload: LoginReq):
    user = verify_user(org_id=payload.org_id, name=payload.name, password=payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(
        {
            "uid": user["id"],
            "org_id": user["org_id"],
            "role": user["role"],
            "name": user["name"],
        }
    )
    return {"access_token": token, "token_type": "bearer"}


@app.post("/v0/orgs")
def api_create_org(payload: OrgCreateReq, x_admin_token: str | None = Header(default=None)):
    verify_admin_token(x_admin_token)
    org_id = create_org(name=payload.name, plan=payload.plan, status=payload.status)
    return {"id": org_id}


@app.get("/v0/orgs")
def api_list_orgs(x_admin_token: str | None = Header(default=None)):
    verify_admin_token(x_admin_token)
    return {"items": list_orgs()}


@app.post("/v0/users")
def api_create_user(payload: UserCreateReq, x_admin_token: str | None = Header(default=None)):
    verify_admin_token(x_admin_token)
    try:
        user_id = create_user(
            org_id=payload.org_id,
            role=payload.role,
            name=payload.name,
            email=payload.email,
            password=payload.password,
        )
        return {"id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v0/users")
def api_list_users(org_id: int | None = None, x_admin_token: str | None = Header(default=None)):
    verify_admin_token(x_admin_token)
    return {"items": list_users(org_id=org_id)}


@app.post("/v0/questions")
def api_create_question(payload: QuestionCreateReq, authorization: str | None = Header(default=None)):
    user = get_current_user(authorization)
    qid = create_question(
        org_id=int(user["org_id"]),
        stem=payload.stem,
        options_json=json.dumps(payload.options, ensure_ascii=False),
        answer=payload.answer,
        analysis=payload.analysis,
        difficulty=payload.difficulty,
        chapter=payload.chapter,
        created_by=int(user["uid"]),
    )
    return {"id": qid}


@app.get("/v0/questions")
def api_list_questions(
    chapter: str | None = None,
    difficulty: str | None = None,
    limit: int = 50,
    authorization: str | None = Header(default=None),
):
    user = get_current_user(authorization)
    items = list_questions(org_id=int(user["org_id"]), chapter=chapter, difficulty=difficulty, limit=limit)
    for item in items:
        item["options"] = json.loads(item.pop("options_json"))
    return {"items": items}


@app.post("/v0/papers/generate")
def api_generate_paper(payload: PaperGenerateReq, authorization: str | None = Header(default=None)):
    user = get_current_user(authorization)
    items = list_questions(
        org_id=int(user["org_id"]),
        chapter=payload.chapter,
        difficulty=payload.difficulty,
        limit=max(payload.num_questions, 1),
    )
    sampled = items[: payload.num_questions]
    for item in sampled:
        item["options"] = json.loads(item.pop("options_json"))
    return {
        "paper": {
            "num_questions": len(sampled),
            "chapter": payload.chapter,
            "difficulty": payload.difficulty,
            "items": sampled,
        }
    }
