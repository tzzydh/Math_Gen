from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.asset import Asset
from app.db.models.diagnostic_task import DiagnosticTask
from app.db.models.user import User
from app.schemas.diagnostic import DiagnosticCreateRequest, DiagnosticResult, DiagnosticTaskResponse
from app.services.diagnostic_service import DiagnosticService

router = APIRouter()


@router.post("", response_model=DiagnosticTaskResponse)
def create_diagnostic(
    payload: DiagnosticCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiagnosticTaskResponse:
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
            detail="asset is not ready for diagnostics",
        )

    task = DiagnosticTask(
        user_id=current_user.id,
        asset_id=asset.id,
        status="processing",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    service = DiagnosticService()
    try:
        processed = service.classify_asset(asset=asset, raw_text=payload.raw_text)
        classification = processed["classification"]
        task.status = "completed"
        task.ocr_result_json = {
            "source": processed["source"],
            "asset_url": processed["asset_url"],
            "text_preview": processed["extracted_text_preview"],
            "questions": processed.get("ocr_questions", []),
        }
        task.knowledge_points_json = classification.get("knowledge_weights", {})
        task.score_json = {
            "chapter": classification.get("chapter"),
            "confidence": classification.get("confidence"),
            "top_matches": classification.get("top_matches", []),
        }
        task.error_message = None
        task.finished_at = datetime.now(timezone.utc)
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)
        task.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(task)
    return _serialize_task(task)


@router.get("/{task_id}", response_model=DiagnosticTaskResponse)
def get_diagnostic(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiagnosticTaskResponse:
    task = db.scalar(
        select(DiagnosticTask).where(
            DiagnosticTask.id == task_id,
            DiagnosticTask.user_id == current_user.id,
        )
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="diagnostic task not found",
        )
    return _serialize_task(task)


def _serialize_task(task: DiagnosticTask) -> DiagnosticTaskResponse:
    score_json = task.score_json or {}
    ocr_json = task.ocr_result_json or {}
    return DiagnosticTaskResponse(
        id=task.id,
        asset_id=task.asset_id,
        status=task.status,
        result=DiagnosticResult(
            chapter=score_json.get("chapter"),
            confidence=score_json.get("confidence"),
            knowledge_weights=task.knowledge_points_json or {},
            top_matches=score_json.get("top_matches", []),
            extracted_text_preview=ocr_json.get("text_preview"),
            source=ocr_json.get("source"),
        ),
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        finished_at=task.finished_at,
    )
