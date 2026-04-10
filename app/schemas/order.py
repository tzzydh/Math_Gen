from pydantic import BaseModel


class OrderCreateRequest(BaseModel):
    diagnostic_id: int
    product_code: str
