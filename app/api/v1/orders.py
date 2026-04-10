from fastapi import APIRouter


router = APIRouter()


@router.get("/placeholder")
def orders_placeholder() -> dict[str, str]:
    return {"message": "orders endpoint scaffolded"}
