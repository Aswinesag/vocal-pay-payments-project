"""Authentication endpoints for user signup, login, and token management.

This module provides secure authentication flows using password-based credentials
and JWT tokens. All endpoints handle async database operations and return
structured Pydantic responses.

Endpoints:
- POST /auth/signup: User registration with password
- POST /auth/login: Credential verification and token generation
- Dependency: get_current_user - JWT token validation and user rehydration
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from loguru import logger
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.database.database import get_async_db
from app.database.models import User
from app.database.schemas import UserCreate, UserResponse


# OAuth2 password bearer for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

router = APIRouter(prefix="/auth", tags=["authentication"])


# ==========================================================
# Response Models
# ==========================================================

class SignupResponse(BaseModel):
    """Response model for successful user registration."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    message: str = "User registered successfully"
    user: UserResponse


class LoginResponse(BaseModel):
    """Response model for successful login with JWT token."""

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(
        description="JWT access token for authenticated requests"
    )
    token_type: str = Field(
        default="bearer",
        description="OAuth2 token type (always 'bearer')",
    )
    user: UserResponse = Field(
        description="Authenticated user information"
    )


# ==========================================================
# Authentication Endpoints
# ==========================================================

@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SignupResponse:
    """Register a new user with password-based authentication."""
    try:
        # Check if email already exists
        existing_user = await db.scalar(
            select(User).where(User.email == user_data.email)
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        
        # Check if phone number already exists
        existing_phone = await db.scalar(
            select(User).where(User.phone_number == user_data.phone_number)
        )
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already registered",
            )
        
        # Hash password securely
        hashed_password = hash_password(user_data.password)
        
        # Generate unique user_id
        user_id = str(uuid.uuid4())
        
        # Create user record with empty biometric embeddings
        new_user = User(
            user_id=user_id,
            full_name=user_data.full_name,
            email=user_data.email,
            phone_number=user_data.phone_number,
            hashed_password=hashed_password,
            speaker_embedding=[],
            face_embedding=[],
            is_active=True,
            is_verified=False,
            preferred_language="en",
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.bind(user_id=user_id, email=user_data.email).info(
            "User registered successfully"
        )
        
        return SignupResponse(user=UserResponse.model_validate(new_user))
        
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        ) from exc
    except Exception as exc:
        await db.rollback()
        logger.bind(error=str(exc)).exception("Signup error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        ) from exc


# ==========================================================
# Authentication Dependencies
# ==========================================================

async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> User:
    """Dependency to extract and validate JWT token from httpOnly cookie.
    
    Args:
        request: FastAPI Request object to access cookies
        db: Async database session
        
    Returns:
        Authenticated User object rehydrated from database
        
    Security Flow:
        1. Extract token from httpOnly cookie (XSS-safe)
        2. Decode and validate JWT signature
        3. Check token expiration
        4. Extract user_id from 'sub' claim
        5. Query database for user
        6. Validate user is active
        
    Raises:
        HTTPException 401: Invalid token, expired, or user not found
        HTTPException 403: User account disabled
        
    Usage:
        @router.get("/protected")
        async def protected_route(
            current_user: User = Depends(get_current_user)
        ):
            return {"user_id": current_user.user_id}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Extract token from httpOnly cookie
    token = request.cookies.get("access_token")
    
    if not token:
        logger.warning("No access_token cookie found")
        raise credentials_exception
    
    try:
        # Decode and validate JWT token
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        
        if user_id is None:
            logger.warning("Token missing 'sub' claim")
            raise credentials_exception
            
    except JWTError as exc:
        logger.bind(error=str(exc)).warning("JWT validation failed")
        raise credentials_exception from exc
    
    # Rehydrate user from database
    user = await db.scalar(
        select(User).where(User.user_id == user_id)
    )
    
    if user is None:
        logger.bind(user_id=user_id).warning("Token valid but user not found")
        raise credentials_exception
    
    # Check if user account is active
    if not user.is_active:
        logger.bind(user_id=user_id).warning("Login attempt with disabled account")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )
    
    return user


async def get_current_active_verified_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Dependency requiring authenticated AND verified user.
    
    Usage for endpoints requiring email verification:
        @router.post("/sensitive-action")
        async def action(user: User = Depends(get_current_active_verified_user)):
            pass
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return current_user


# ==========================================================
# User Info & Authentication Endpoints
# ==========================================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Get current authenticated user information from httpOnly cookie.
    
    Returns user details for authenticated session.
    Validates JWT token from cookie automatically.
    """
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Logout user by clearing httpOnly cookie.
    
    Removes access_token cookie, effectively logging out the user.
    """
    response.delete_cookie(
        key="access_token",
        path="/",
        domain=None,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="lax"
    )
    logger.info("User logged out successfully")
    return {"message": "Logged out successfully"}


@router.post("/login")
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_async_db)],
):
    """Authenticate user and set secure httpOnly cookie with JWT token.
    
    Security Implementation:
        - JWT token stored in httpOnly cookie (not accessible to JavaScript)
        - Secure flag enforces HTTPS transmission only
        - SameSite=lax prevents CSRF attacks
        - No token in response body (defense-in-depth)
    """
    try:
        # Find user by email (username field contains email)
        user = await db.scalar(
            select(User).where(User.email == form_data.username)
        )
        
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account disabled",
            )
        
        # Create JWT access token
        access_token = create_access_token(data={"sub": user.user_id})
        
        # Set secure httpOnly cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,  # Not accessible to JavaScript (XSS protection)
            secure=settings.COOKIE_SECURE,
            samesite="lax",  # CSRF protection
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Seconds
            path="/",        # Available across entire domain
        )
        
        # Update last login
        from app.database.models import utc_now_naive
        user.last_login_at = utc_now_naive()
        await db.commit()
        
        logger.bind(user_id=user.user_id).info("Login successful - secure cookie set")
        
        # Return user data only (NO TOKEN in body)
        return {
            "success": True,
            "message": "Authentication successful",
            "user": UserResponse.model_validate(user).model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.bind(error=str(exc)).exception("Login error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed",
        ) from exc
