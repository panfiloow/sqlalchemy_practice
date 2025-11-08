from datetime import datetime
from typing import List
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    username: str
    email: EmailStr

class CreateUser(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class UsersListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    size: int
    pages: int