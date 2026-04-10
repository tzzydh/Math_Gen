from pydantic import BaseModel, Field


class WechatLoginRequest(BaseModel):
    code: str
    nickname: str | None = Field(default=None, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=512)


class UserProfile(BaseModel):
    id: int
    openid: str
    unionid: str | None = None
    nickname: str | None = None
    avatar_url: str | None = None
    status: str


class WechatLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: bool
    user: UserProfile
