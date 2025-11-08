from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_refresh_token
from app.database import get_async_session
from app.schemas.auth import UserLogin, TokenResponse, LogoutResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.api.dependencies import get_auth_service, get_current_active_user
from app.core.cookies import set_auth_cookies, delete_auth_cookies
from app.config import settings
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post(
    "/login",
    response_model=UserResponse,
    summary="User login",
    description="Authenticate user and set JWT tokens"
)
async def login(
    response: Response,
    user_data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_async_session)
):
    user = await auth_service.authenticate_user(
        user_data.username, 
        user_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    access_token, refresh_token = await auth_service.create_tokens(str(user.id))
    set_auth_cookies(response, access_token, refresh_token)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at
    )

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token"
)
async def refresh_token(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    refresh_token = request.cookies.get(settings.COOKIE_REFRESH_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token found")
    
    try:
        access_token, new_refresh_token = await auth_service.refresh_tokens(refresh_token)
        set_auth_cookies(response, access_token, new_refresh_token)
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            message="Tokens refreshed successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post(
    "/logout",
    summary="User logout"
)
async def logout(
    response: Response,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    refresh_token = request.cookies.get(settings.COOKIE_REFRESH_NAME)
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            token_jti = payload.get("jti")
            if token_jti:
                await auth_service.logout(token_jti)
        except JWTError:
            pass
    
    delete_auth_cookies(response)
    return {"message": "Successfully logged out"}

@router.post(
    "/logout-all",
    response_model=LogoutResponse,
    summary="Logout from all devices"
)
async def logout_all(
    response: Response,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    user_id = str(current_user.id)
    revoked_count = await auth_service.logout_all(user_id)
    
    delete_auth_cookies(response)
    
    return LogoutResponse(
        message="Successfully logged out from all devices",
        user_id=user_id,
        tokens_revoked=revoked_count,
        username=current_user.username
    )