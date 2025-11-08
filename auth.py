from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Request, Response, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select
from database import get_async_session
from models import RefreshToken, User
import secrets

# Конфигурация
SECRET_KEY = "your-secret-key-change-in-production"
REFRESH_SECRET_KEY = "your-refresh-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30
COOKIE_ACCESS_NAME = "access_token"
COOKIE_REFRESH_NAME = "refresh_token"

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Функции для паролей
def hash_password(password: str) -> str:
    """Хеширует пароль"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль"""
    return pwd_context.verify(plain_password, hashed_password)

# Функции создания токенов
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создает короткоживущий access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """Создает refresh token БЕЗ сохранения в БД"""
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.utcnow() + expires_delta
    
    token_jti = secrets.token_urlsafe(32)
    data.update({
        "exp": expire, 
        "type": "refresh",
        "jti": token_jti
    })
    
    return jwt.encode(data, REFRESH_SECRET_KEY, algorithm=ALGORITHM)

# Функции работы с БД
async def save_refresh_token(db: AsyncSession, user_id: str, token_jti: str):
    """Сохраняет refresh token в БД (БЕЗ коммита)"""
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    db_refresh_token = RefreshToken(
        user_id=user_id,
        token_jti=token_jti,
        expires_at=expires_at
    )
    
    db.add(db_refresh_token)

async def create_and_save_refresh_token(db: AsyncSession, user_id: str) -> str:
    """Создает refresh token и сохраняет в БД (для login)"""
    token_jti = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    refresh_token = jwt.encode(
        {
            "sub": user_id,
            "type": "refresh",
            "jti": token_jti,
            "exp": expires_at
        },
        REFRESH_SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    db_refresh_token = RefreshToken(
        user_id=user_id,
        token_jti=token_jti,
        expires_at=expires_at
    )
    
    db.add(db_refresh_token)
    await db.commit()
    
    return refresh_token

async def revoke_user_tokens(db: AsyncSession, user_id: str) -> int:
    """Отзывает все refresh tokens пользователя и возвращает количество"""
    try:
        print(f"🔍 REVOKE_DEBUG: Starting revocation for user: {user_id}")
        print(f"🔍 REVOKE_DEBUG: User ID type: {type(user_id)}, value: {user_id}")
        
        # 1. Сначала проверим существование таблицы и токенов
        count_stmt = select(func.count(RefreshToken.id)).where(RefreshToken.user_id == user_id)
        print(f"🔍 REVOKE_DEBUG: Count SQL: {count_stmt}")
        
        count_result = await db.execute(count_stmt)
        tokens_count = count_result.scalar_one()
        print(f"🔍 REVOKE_DEBUG: Found {tokens_count} tokens for user")
        
        if tokens_count == 0:
            print("ℹ️ REVOKE_DEBUG: No tokens to revoke")
            return 0
        
        # 2. Выполняем удаление
        delete_stmt = delete(RefreshToken).where(RefreshToken.user_id == user_id)
        print(f"🔍 REVOKE_DEBUG: Delete SQL: {delete_stmt}")
        
        result = await db.execute(delete_stmt)
        deleted_count = result.rowcount
        
        print(f"✅ REVOKE_DEBUG: Successfully deleted {deleted_count} tokens")
        return deleted_count
        
    except Exception as e:
        print(f"❌ REVOKE_DEBUG: Error in revoke_user_tokens: {e}")
        print(f"❌ REVOKE_DEBUG: Error type: {type(e).__name__}")
        import traceback
        print(f"❌ REVOKE_DEBUG: Traceback: {traceback.format_exc()}")
        raise

async def revoke_token(db: AsyncSession, token_jti: str) -> int:
    """Отзывает конкретный refresh token и возвращает количество"""
    result = await db.execute(
        delete(RefreshToken).where(RefreshToken.token_jti == token_jti)
    )
    return result.rowcount

# Функции аутентификации
async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """Аутентифицирует пользователя по username и password"""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    
    return user

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> User:
    """Получает текущего пользователя из access token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    token = request.cookies.get(COOKIE_ACCESS_NAME)
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
            
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user

async def verify_refresh_token(
    request: Request,
    db: AsyncSession
) -> User:
    """Верифицирует refresh token и возвращает пользователя"""
    refresh_token = request.cookies.get(COOKIE_REFRESH_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    
    try:
        payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Not a refresh token")
            
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="No user ID in token")
            
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {str(e)}")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Проверяет что пользователь активен"""
    return current_user

# Функции работы с cookies
def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Устанавливает access и refresh токены в cookies"""
    # Access token
    response.set_cookie(
        key=COOKIE_ACCESS_NAME,
        value=access_token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    
    # Refresh token
    response.set_cookie(
        key=COOKIE_REFRESH_NAME,
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )

def delete_auth_cookies(response: Response):
    """Удаляет все auth cookies"""
    response.delete_cookie(COOKIE_ACCESS_NAME, path="/")
    response.delete_cookie(COOKIE_REFRESH_NAME, path="/")