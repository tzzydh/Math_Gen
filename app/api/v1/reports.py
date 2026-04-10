from fastapi import APIRouter


router = APIRouter()


@router.get("/placeholder")
def reports_placeholder() -> dict[str, str]:
    return {"message": "reports endpoint scaffolded"}
