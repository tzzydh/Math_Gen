from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.gaokao_plan import GaokaoPlan
from app.db.models.user import User
from app.schemas.gaokao import (
    GaokaoControlLineItem,
    GaokaoDirectionCard,
    GaokaoPlanRequest,
    GaokaoPlanResponse,
    GaokaoPlanSummary,
    GaokaoRecommendation,
)
from app.services.gaokao_service import GaokaoService

router = APIRouter()


@router.post("/plan", response_model=GaokaoPlanResponse)
def create_gaokao_plan(
    payload: GaokaoPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GaokaoPlanResponse:
    service = GaokaoService(db)
    try:
        result = service.build_plan(payload)
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

    plan = GaokaoPlan(
        user_id=current_user.id,
        province=payload.province,
        subject_combination=payload.subject_combination,
        score=payload.score,
        rank=payload.rank,
        target_json={
            "preferred_majors": payload.preferred_majors,
            "preferred_cities": payload.preferred_cities,
            "career_preferences": payload.career_preferences,
            "family_budget": payload.family_budget,
            "notes": payload.notes,
        },
        summary=result["summary"],
        details_json={
            "year": result["year"],
            "track": result["track"],
            "calculated_rank": result["calculated_rank"],
            "direction_advice": result["direction_advice"],
            "direction_cards": result["direction_cards"],
            "strategy": result["strategy"],
            "risk_notes": result["risk_notes"],
            "control_lines": result["control_lines"],
            "recommendations": result["recommendations"],
        },
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


@router.get("", response_model=list[GaokaoPlanSummary])
def list_gaokao_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GaokaoPlanSummary]:
    plans = list(
        db.scalars(
            select(GaokaoPlan)
            .where(GaokaoPlan.user_id == current_user.id)
            .order_by(desc(GaokaoPlan.created_at))
            .limit(20)
        )
    )
    return [
        GaokaoPlanSummary(
            plan_id=plan.id,
            province=plan.province,
            score=plan.score,
            subject_combination=plan.subject_combination,
            summary=plan.summary,
            created_at=plan.created_at,
        )
        for plan in plans
    ]


@router.get("/{plan_id}", response_model=GaokaoPlanResponse)
def get_gaokao_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GaokaoPlanResponse:
    plan = db.scalar(
        select(GaokaoPlan).where(
            GaokaoPlan.id == plan_id,
            GaokaoPlan.user_id == current_user.id,
        )
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="gaokao plan not found",
        )
    return _serialize_plan(plan)


def _serialize_plan(plan: GaokaoPlan) -> GaokaoPlanResponse:
    details = plan.details_json or {}
    recommendations = [
        GaokaoRecommendation(**item)
        for item in details.get("recommendations", [])
        if isinstance(item, dict)
    ]
    control_lines = [
        GaokaoControlLineItem(**item)
        for item in details.get("control_lines", [])
        if isinstance(item, dict)
    ]
    direction_cards = [
        GaokaoDirectionCard(**item)
        for item in details.get("direction_cards", [])
        if isinstance(item, dict)
    ]
    return GaokaoPlanResponse(
        plan_id=plan.id,
        province=plan.province,
        year=int(details.get("year", 2025)),
        track=str(details.get("track", "physics")),
        score=plan.score,
        rank=plan.rank,
        calculated_rank=int(details.get("calculated_rank", 0)),
        subject_combination=plan.subject_combination,
        summary=plan.summary,
        direction_advice=details.get("direction_advice", []),
        direction_cards=direction_cards,
        strategy=details.get("strategy", []),
        risk_notes=details.get("risk_notes", []),
        control_lines=control_lines,
        recommendations=recommendations,
        created_at=plan.created_at,
    )
