from fastapi import Response
from app.config import settings

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set access and refresh tokens in cookies"""
    # Access token
    response.set_cookie(
        key=settings.COOKIE_ACCESS_NAME,
        value=access_token,
        httponly=False,
        secure=not settings.DEBUG,  # Secure in production
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    
    # Refresh token
    response.set_cookie(
        key=settings.COOKIE_REFRESH_NAME,
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )

def delete_auth_cookies(response: Response):
    """Delete all auth cookies"""
    response.delete_cookie(settings.COOKIE_ACCESS_NAME, path="/")
    response.delete_cookie(settings.COOKIE_REFRESH_NAME, path="/")