from database import Base
from sqlalchemy import Boolean, ForeignKey, String, Column, DateTime, func
import uuid
from sqlalchemy.orm import relationship


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_jti = Column(String(64), unique=True, nullable=False, index=True)  # JWT ID
    is_revoked = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="refresh_tokens")


class User(Base):

    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    username = Column(String(50), nullable=False, unique=True,index=True)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(60), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    refresh_tokens = relationship("RefreshToken", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"