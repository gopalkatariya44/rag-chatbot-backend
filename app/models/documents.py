from datetime import datetime

from pydantic import BaseModel, UUID4


class DocumentCreate(BaseModel):
    filename: str
    file_type: str


class DocumentOut(BaseModel):
    id: UUID4
    filename: str
    file_type: str
    uploaded_at: datetime
    processed: bool
    status: str
    file_path: str

    class Config:
        from_attributes = True  # Enables ORM mode for Pydantic
