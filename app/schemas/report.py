from pydantic import BaseModel


class ReportCreateRequest(BaseModel):
    diagnostic_id: int
    order_id: int
