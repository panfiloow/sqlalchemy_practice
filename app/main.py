from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from app.api.dependencies import get_current_active_user
from app.config import settings
from app.database import engine
from app.api.routes import auth_router, users_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan для очистки ресурсов"""
    print("🚀 Starting FastAPI application")
    yield
    print("🛑 Shutting down FastAPI application")
    await engine.dispose()

app = FastAPI(
    title="Education API", 
    version="1.0.0", 
    lifespan=lifespan,
    debug=settings.DEBUG
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")

# Health check
@app.get(
    "/",
    summary="Health check",
    description="Check if the server is running"
)
async def root():
    return {
        "status": "healthy",
        "message": "Server is running",
        "version": "1.0.0",
        "environment": "development" if settings.DEBUG else "production"
    }

@app.get("/api/v1/protected", summary="Protected endpoint example")
async def protected_route(current_user = Depends(get_current_active_user)):
    return {
        "message": f"Hello {current_user.username}!",
        "user_id": str(current_user.id),
        "email": current_user.email
    }