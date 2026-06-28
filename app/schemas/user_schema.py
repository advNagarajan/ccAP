from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "USER"


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    user_id: UUID
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserRoleUpdate(BaseModel):
    role: str


class UserChangePassword(BaseModel):
    current_password: str
    new_password: str


