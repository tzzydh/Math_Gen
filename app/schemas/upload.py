from pydantic import BaseModel, Field


class UploadPresignRequest(BaseModel):
    filename: str
    content_type: str
    directory: str = Field(default="questions", max_length=64)


class UploadPresignResponse(BaseModel):
    asset_id: int
    object_key: str
    upload_host: str
    upload_method: str = "POST"
    form_data: dict[str, str]
    public_url: str
    expires_in: int


class UploadConfirmRequest(BaseModel):
    asset_id: int
    size: int | None = None
    sha256: str | None = Field(default=None, max_length=64)
    mime_type: str | None = Field(default=None, max_length=128)


class UploadConfirmResponse(BaseModel):
    asset_id: int
    object_key: str
    status: str
    public_url: str
