from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models.asset import Asset
from app.db.models.essay_review import EssayReview
from app.db.models.user import User
from app.schemas.essay import (
    EssayCorrectionRequest,
    EssayCorrectionResponse,
    EssayReviewDetail,
    EssayReviewSummary,
)
from app.services.essay_service import EssayService

router = APIRouter()


@router.post("/correct", response_model=EssayCorrectionResponse)
def correct_essay(
    payload: EssayCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EssayCorrectionResponse:
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
    if asset.status != "uploaded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="asset is not ready for essay correction",
        )

    service = EssayService()
    try:
        result = service.correct_asset(
            asset=asset,
            subject=payload.subject,
            raw_text=payload.raw_text,
            title=payload.title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    pdf_object_key = service.oss_service.build_object_key(
        user_id=current_user.id,
        filename=f"{result['subject']}-essay-review.pdf",
        directory="essay-reports",
    )
    service.oss_service.put_object(
        object_key=pdf_object_key,
        content=result["pdf_bytes"],
        content_type="application/pdf",
    )

    pdf_asset = Asset(
        user_id=current_user.id,
        bucket_provider=settings.oss_provider,
        bucket_name=service.oss_service.bucket.bucket_name,
        object_key=pdf_object_key,
        mime_type="application/pdf",
        size=len(result["pdf_bytes"]),
        status="uploaded",
    )
    db.add(pdf_asset)
    db.flush()

    review = EssayReview(
        user_id=current_user.id,
        source_asset_id=asset.id,
        pdf_asset_id=pdf_asset.id,
        status="completed",
        subject=result["subject"],
        source=result["source"],
        recognized_title=result["recognized_title"] or None,
        corrected_title=result["corrected_title"],
        recognized_text=result["recognized_text"],
        corrected_text=result["corrected_text"],
        summary=result["summary"],
        score=result["score"],
        score_max=result["score_max"],
        details_json={
            "strengths": result["strengths"],
            "issues": result["issues"],
            "suggestions": result["suggestions"],
        },
        finished_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return _serialize_review(
        review=review,
        asset_id=asset.id,
        pdf_url=service.oss_service.public_url(pdf_object_key),
    )


@router.get("", response_model=list[EssayReviewSummary])
def list_essay_reviews(
    subject: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EssayReviewSummary]:
    query = select(EssayReview).where(EssayReview.user_id == current_user.id)
    if subject:
        query = query.where(EssayReview.subject == subject.strip().lower())
    reviews = list(
        db.scalars(
            query.order_by(desc(EssayReview.created_at)).limit(20)
        )
    )
    oss = EssayService().oss_service
    return [
        EssayReviewSummary(
            review_id=review.id,
            subject=review.subject,
            corrected_title=review.corrected_title,
            score=review.score,
            score_max=review.score_max,
            created_at=review.created_at,
            pdf_url=oss.public_url(review.pdf_asset.object_key),
        )
        for review in reviews
    ]


@router.get("/{review_id}", response_model=EssayReviewDetail)
def get_essay_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EssayReviewDetail:
    review = db.scalar(
        select(EssayReview).where(
            EssayReview.id == review_id,
            EssayReview.user_id == current_user.id,
        )
    )
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="essay review not found",
        )
    return EssayReviewDetail(
        **_serialize_review(
            review=review,
            asset_id=review.source_asset_id,
            pdf_url=EssayService().oss_service.public_url(review.pdf_asset.object_key),
        ).model_dump(),
        created_at=review.created_at,
    )


@router.get("/{review_id}/pdf-download")
def download_essay_pdf(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    review = db.scalar(
        select(EssayReview).where(
            EssayReview.id == review_id,
            EssayReview.user_id == current_user.id,
        )
    )
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="essay review not found",
        )
    if review.pdf_asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="pdf asset not found",
        )

    service = EssayService()
    try:
        pdf_bytes = service.download_asset_bytes(review.pdf_asset)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    filename = f"{review.subject}-essay-review-{review.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


def _serialize_review(review: EssayReview, asset_id: int, pdf_url: str) -> EssayCorrectionResponse:
    details = review.details_json or {}
    return EssayCorrectionResponse(
        review_id=review.id,
        asset_id=asset_id,
        subject=review.subject,
        source=review.source,
        recognized_title=review.recognized_title,
        recognized_text=review.recognized_text,
        corrected_title=review.corrected_title,
        corrected_text=review.corrected_text,
        summary=review.summary,
        score=review.score,
        score_max=review.score_max,
        strengths=details.get("strengths", []),
        issues=details.get("issues", []),
        suggestions=details.get("suggestions", []),
        pdf_asset_id=review.pdf_asset_id,
        pdf_url=pdf_url,
    )
