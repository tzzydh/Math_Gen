from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.deps import get_current_user, get_db
from app.db.models.asset import Asset
from app.db.models.user import User
from app.schemas.upload import (
    UploadConfirmRequest,
    UploadConfirmResponse,
    UploadPresignRequest,
    UploadPresignResponse,
)
from app.services.oss import OssService

router = APIRouter()


@router.post("/presign", response_model=UploadPresignResponse)
def presign_upload(
    payload: UploadPresignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadPresignResponse:
    if not payload.filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filename is required",
        )

    oss = OssService()
    try:
        object_key = oss.build_object_key(
            user_id=current_user.id,
            filename=payload.filename,
            directory=payload.directory,
        )
        upload_policy = oss.generate_post_policy(
            object_key=object_key,
            content_type=payload.content_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    asset = Asset(
        user_id=current_user.id,
        bucket_provider=settings.oss_provider,
        bucket_name=oss.bucket.bucket_name,
        object_key=object_key,
        mime_type=payload.content_type,
        status="presigned",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return UploadPresignResponse(
        asset_id=asset.id,
        object_key=object_key,
        upload_host=upload_policy["upload_host"],
        form_data=upload_policy["form_data"],
        public_url=oss.public_url(object_key),
        expires_in=int(upload_policy["expires_in"]),
    )


@router.post("/confirm", response_model=UploadConfirmResponse)
def confirm_upload(
    payload: UploadConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadConfirmResponse:
    asset = db.scalar(
        select(Asset).where(
            Asset.id == payload.asset_id,
            Asset.user_id == current_user.id,
        )
    )
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="asset not found",
        )

    if payload.size is not None:
        asset.size = payload.size
    if payload.sha256:
        asset.sha256 = payload.sha256
    if payload.mime_type:
        asset.mime_type = payload.mime_type
    asset.status = "uploaded"

    db.commit()
    db.refresh(asset)

    return UploadConfirmResponse(
        asset_id=asset.id,
        object_key=asset.object_key,
        status=asset.status,
        public_url=OssService().public_url(asset.object_key),
    )
