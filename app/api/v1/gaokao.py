from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.gaokao_plan import GaokaoPlan
from app.db.models.user import User
from app.schemas.gaokao import (
    GaokaoConsultationResponse,
    GaokaoConsultationRequest,
    GaokaoControlLineItem,
    GaokaoDirectionCard,
    GaokaoExtendedRecommendation,
    GaokaoPlanRequest,
    GaokaoPlanResponse,
    GaokaoPlanSummary,
    GaokaoRecommendation,
)
from app.services.gaokao_report_service import GaokaoReportService
from app.services.gaokao_service import GaokaoService

router = APIRouter()


@router.post("/consultation", response_model=GaokaoConsultationResponse)
def gaokao_consultation(
    payload: GaokaoConsultationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GaokaoConsultationResponse:
    del current_user
    service = GaokaoService(db)
    try:
        result = service.build_consultation(payload)
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
    return GaokaoConsultationResponse(**result)


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
            "advisor_mode": result["advisor_mode"],
            "advisor_model": result["advisor_model"],
            "llm_enhanced": result["llm_enhanced"],
            "advisor_engine_note": result["advisor_engine_note"],
            "direction_advice": result["direction_advice"],
            "direction_cards": result["direction_cards"],
            "advisor_takeaways": result["advisor_takeaways"],
            "school_choice_logic": result["school_choice_logic"],
            "major_observations": result["major_observations"],
            "major_breakdown": result["major_breakdown"],
            "signature_advice": result["signature_advice"],
            "school_pool_note": result["school_pool_note"],
            "extended_pool": result["extended_pool"],
            "deep_analysis": result["deep_analysis"],
            "strategy": result["strategy"],
            "risk_notes": result["risk_notes"],
            "execution_checklist": result["execution_checklist"],
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


@router.get("/{plan_id}/pdf-download")
def download_gaokao_plan_pdf(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
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

    try:
        pdf_bytes = GaokaoReportService().build_pdf_bytes(plan)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    filename = f"gaokao-plan-{plan.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


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
    major_breakdown = [
        GaokaoDirectionCard(**item)
        for item in details.get("major_breakdown", [])
        if isinstance(item, dict)
    ]
    extended_pool = [
        GaokaoExtendedRecommendation(**item)
        for item in details.get("extended_pool", [])
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
        advisor_mode=str(details.get("advisor_mode", "rules_only")),
        advisor_model=details.get("advisor_model"),
        llm_enhanced=bool(details.get("llm_enhanced", False)),
        advisor_engine_note=details.get("advisor_engine_note"),
        direction_advice=details.get("direction_advice", []),
        direction_cards=direction_cards,
        advisor_takeaways=details.get("advisor_takeaways", []),
        school_choice_logic=details.get("school_choice_logic", []),
        major_observations=details.get("major_observations", []),
        major_breakdown=major_breakdown,
        signature_advice=details.get("signature_advice", []),
        school_pool_note=details.get("school_pool_note"),
        extended_pool=extended_pool,
        deep_analysis=details.get("deep_analysis", []),
        strategy=details.get("strategy", []),
        risk_notes=details.get("risk_notes", []),
        execution_checklist=details.get("execution_checklist", []),
        control_lines=control_lines,
        recommendations=recommendations,
        created_at=plan.created_at,
    )
