from fastapi import APIRouter

from app.api.v1 import auth, diagnostics, essays, gaokao, health, orders, reports, uploads


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(diagnostics.router, prefix="/diagnostics", tags=["diagnostics"])
api_router.include_router(essays.router, prefix="/essays", tags=["essays"])
api_router.include_router(gaokao.router, prefix="/gaokao", tags=["gaokao"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
