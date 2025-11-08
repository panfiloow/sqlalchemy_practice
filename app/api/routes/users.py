from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.schemas.user import UserResponse, CreateUser, UsersListResponse
from app.services.user_service import UserService
from app.api.dependencies import get_user_service, get_current_active_user
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])

@router.post(
    "/",
    response_model=UserResponse,
    status_code=201,
    summary="Register new user"
)
async def register_user(
    user_data: CreateUser,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.create_user(
        user_data.username,
        user_data.email,
        user_data.password
    )

@router.get(
    "/",
    response_model=UsersListResponse,
    summary="List users with pagination"
)
async def list_users(
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Page size")] = 10,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.get_users_paginated(page, size)

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user"
)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at
    )