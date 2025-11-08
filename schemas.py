from datetime import datetime
from typing import List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator

class CreateUser(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["john_doe"])
    email: EmailStr = Field(..., example="user@example.com")
    password: str = Field(..., min_length=8, example="securepassword123")

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, underscores and hyphens')
        return v

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    created_at: datetime
    
    model_config = {
        "from_attributes": True  
    }

class UsersListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    size: int
    pages: int

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(10, ge=1, le=100, description="Page size")


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenRefresh(BaseModel):
    access_token: str
    token_type: str


class UserLogin(BaseModel):
    username: str = Field(..., examples=["john_doe"])
    password: str = Field(..., example="securepassword123")