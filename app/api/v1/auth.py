import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.user import User
from app.schemas.auth import UserProfile, WechatLoginRequest, WechatLoginResponse
from app.services.wechat_auth import code2session

router = APIRouter()


@router.post("/wechat/login", response_model=WechatLoginResponse)
async def wechat_login(
    payload: WechatLoginRequest,
    db: Session = Depends(get_db),
) -> WechatLoginResponse:
    if not settings.wechat_appid or not settings.wechat_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="wechat app credentials not configured",
        )

    try:
        session_data = await code2session(
            appid=settings.wechat_appid,
            secret=settings.wechat_secret,
            code=payload.code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="wechat api unavailable",
        ) from exc

    openid = session_data["openid"]
    unionid = session_data.get("unionid")
    user = db.scalar(select(User).where(User.openid == openid))
    is_new_user = user is None

    if user is None:
        user = User(
            openid=openid,
            unionid=unionid,
            nickname=payload.nickname,
            avatar_url=payload.avatar_url,
            status="active",
        )
        db.add(user)
        db.flush()
    else:
        if unionid and user.unionid != unionid:
            user.unionid = unionid
        if payload.nickname:
            user.nickname = payload.nickname
        if payload.avatar_url:
            user.avatar_url = payload.avatar_url

    db.commit()
    db.refresh(user)

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "uid": user.id,
            "openid": user.openid,
        },
    )

    return WechatLoginResponse(
        access_token=access_token,
        is_new_user=is_new_user,
        user=UserProfile(
            id=user.id,
            openid=user.openid,
            unionid=user.unionid,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            status=user.status,
        ),
    )
