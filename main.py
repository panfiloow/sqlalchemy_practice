from datetime import datetime
import os
from typing import Annotated
from fastapi import FastAPI, HTTPException, Query, Request, Response, status, Depends
from sqlalchemy import func, select
from auth import (
    ALGORITHM, COOKIE_REFRESH_NAME, REFRESH_SECRET_KEY,
    authenticate_user, create_access_token, create_and_save_refresh_token,
    create_refresh_token, delete_auth_cookies, get_current_active_user,
    hash_password, revoke_token, revoke_user_tokens,
    save_refresh_token, set_auth_cookies, verify_refresh_token
)
from database import engine, get_async_session
from models import User
from schemas import UserLogin, UserResponse, CreateUser, UsersListResponse
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

async def lifespan(app: FastAPI):
    """Lifespan для очистки ресурсов"""
    print("🚀 Starting FastAPI application")
    yield
    print("🛑 Shutting down FastAPI application")
    await engine.dispose()

app = FastAPI(title="Education API", version="1.0.0", lifespan=lifespan)
USERS_PREFIX = "/api/v1/users"

# Health check
@app.get(
    "/",
    summary="Health check",
    description="Check if the server is running and get basic API information",
    response_description="Server status and metadata"
)
async def root():
    return {
        "status": "healthy",
        "message": "Server is running",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

# Регистрация пользователя
@app.post(
    "/api/v1/users/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account"
)
async def register_user(
    user_data: CreateUser,
    db: AsyncSession = Depends(get_async_session)
):
    existing_user = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    
    hashed_password = hash_password(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user

# Список пользователей с пагинацией
@app.get(
    f"{USERS_PREFIX}/",
    response_model=UsersListResponse,
    summary="List users with pagination",
    description="Get paginated list of all users in the system"
)
async def list_users(
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Page size")] = 10,
    db: AsyncSession = Depends(get_async_session)
):
    offset = (page - 1) * size
    
    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar_one()
    
    users_result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    users = users_result.scalars().all()
    
    pages = (total + size - 1) // size
    
    return UsersListResponse(
        items=users,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

# Аутентификация - ИСПРАВЛЕННЫЙ login
@app.post(
    "/api/v1/auth/login",
    response_model=UserResponse,
    summary="User login",
    description="Authenticate user and set JWT tokens"
)
async def login(
    response: Response,
    user_data: UserLogin,
    db: AsyncSession = Depends(get_async_session)
):
    # Аутентифицируем пользователя
    user = await authenticate_user(db, user_data.username, user_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # ⚠️ ВАЖНО: Сохраняем данные ДО создания токенов
    user_data_for_response = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at
    }
    
    # Создаем токены
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_and_save_refresh_token(db, str(user.id))
    
    set_auth_cookies(response, access_token, refresh_token)
    
    # Возвращаем сохраненные данные (не ORM объект)
    return UserResponse(**user_data_for_response)

# Refresh token
@app.post(
    "/api/v1/auth/refresh",
    summary="Refresh access token",
    description="Get new access token using refresh token"
)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_session)
):
    try:
        user = await verify_refresh_token(request, db)
        
        refresh_token_cookie = request.cookies.get(COOKIE_REFRESH_NAME)
        if not refresh_token_cookie:
            raise HTTPException(status_code=401, detail="No refresh token found")
        
        # Отзываем старый токен
        old_payload = jwt.decode(refresh_token_cookie, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        token_jti = old_payload.get("jti")
        
        if token_jti:
            await revoke_token(db, token_jti)
        
        # Создаем новые токены
        new_access_token = create_access_token(data={"sub": str(user.id)})
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        # Сохраняем новый токен
        new_payload = jwt.decode(new_refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        new_token_jti = new_payload.get("jti")
        
        if new_token_jti:
            await save_refresh_token(db, str(user.id), new_token_jti)
        
        await db.commit()
        set_auth_cookies(response, new_access_token, new_refresh_token)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "message": "Tokens refreshed successfully"
        }
        
    except HTTPException:
        await db.rollback()
        raise
    except JWTError as e:
        await db.rollback()
        raise HTTPException(status_code=401, detail=f"Token error: {str(e)}")
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

# Logout
@app.post(
    "/api/v1/auth/logout",
    summary="User logout",
    description="Clear authentication cookies and revoke current refresh token"
)
async def logout(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_async_session)
):
    refresh_token = request.cookies.get(COOKIE_REFRESH_NAME)
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            token_jti = payload.get("jti")
            if token_jti:
                await revoke_token(db, token_jti)
                await db.commit()
        except JWTError:
            pass
    
    delete_auth_cookies(response)
    return {"message": "Successfully logged out"}

# Logout all devices
@app.post("/api/v1/auth/logout-all")
async def logout_all(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Logout from all devices and sessions.
    """
    try:
        print(f"🚪 Logout-all for user: {current_user.username}")
        
        # ⚠️ ВАЖНО: Сохраняем все данные ДО операций с БД
        user_data = {
            "user_id": str(current_user.id),      # Сохраняем ДО коммита
            "username": current_user.username     # Сохраняем ДО коммита
        }
        print(f"🔍 User data saved: {user_data}")
        
        # 1. Отзываем все токены
        revoked_count = await revoke_user_tokens(db, user_data["user_id"])
        print(f"✅ Tokens revoked: {revoked_count}")
        
        # 2. Коммитим изменения
        await db.commit()
        print("✅ Database committed")
        
        # 3. Очищаем cookies
        delete_auth_cookies(response)
        print("✅ Cookies cleared")
        
        # 4. Возвращаем ответ с СОХРАНЕННЫМИ данными (не обращаемся к current_user!)
        return {
            "message": "Successfully logged out from all devices",
            "user_id": user_data["user_id"],      # Используем сохраненные данные
            "tokens_revoked": revoked_count,
            "username": user_data["username"]     # Используем сохраненные данные
        }
        
    except Exception as e:
        print(f"❌ ERROR in logout-all: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Logout failed")
    
# Защищенные эндпоинты
@app.get(
    "/api/v1/users/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get information about currently authenticated user"
)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    # ⚠️ ВАЖНО: Сохраняем данные перед возвратом
    user_data = {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "created_at": current_user.created_at
    }
    return UserResponse(**user_data)

@app.get(
    "/api/v1/protected",
    summary="Protected endpoint example",
    description="Example of JWT-protected endpoint"
)
async def protected_route(current_user: User = Depends(get_current_active_user)):
    return {
        "message": f"Hello {current_user.username}!",
        "user_id": str(current_user.id),
        "email": current_user.email
    }