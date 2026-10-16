"""Shapes of request and response bodies. Pydantic validates incoming data against them.

Response schemas are also a security boundary: UserOut has no password_hash field,
so it can never be sent to a client by accident.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # build it straight from a User object

    id: int
    email: str
    role: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int        # seconds
