from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(ORMModel):
    id: UUID
    email: EmailStr
    name: str
    role: UserRole
    department: str | None = None
    manager_id: UUID | None = None

