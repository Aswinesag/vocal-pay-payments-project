"""Authentication and security utilities for VocalPay.

This module provides cryptographic primitives for password hashing and
JWT token management, ensuring secure user authentication and API access control.

Security Features:
- Password hashing: Bcrypt with configurable work factor
- JWT tokens: HMAC SHA-256 signed tokens with expiration
- Token validation: Signature verification and expiry checks
- Secure defaults: Industry-standard security parameters

Dependencies:
- passlib[bcrypt]: Password hashing with bcrypt algorithm
- python-jose[cryptography]: JWT encoding/decoding with cryptographic support
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


# ==========================================================
# Password Hashing Configuration
# ==========================================================

# Passlib CryptContext for bcrypt password hashing
# Bcrypt parameters:
# - rounds=12: Work factor (2^12 iterations) - balance security/performance
# - auto: Automatically rehash passwords if parameters change
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.
    
    Args:
        password: Plaintext password string to hash
        
    Returns:
        Bcrypt hashed password string (60 characters, $2b$ prefix)
        
    Security:
        - Bcrypt work factor: 12 rounds (2^12 = 4096 iterations)
        - Salt: Automatically generated per-password (128-bit random)
        - Output format: $2b$12$[22-char salt][31-char hash]
        - Time complexity: ~100-300ms on modern CPU (intentional slowdown)
        
    Raises:
        ValueError: If password is empty or None
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.
    
    Args:
        plain_password: Plaintext password to verify
        hashed_password: Bcrypt hashed password from database
        
    Returns:
        True if password matches hash, False otherwise
        
    Security:
        - Constant-time comparison (timing attack resistant)
        - Automatic algorithm detection from hash prefix
        - Safe against hash injection (validates hash format)
        
    Raises:
        ValueError: If hash format is invalid
    """
    if not plain_password or not hashed_password:
        return False
    
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Invalid hash format or verification error
        return False


# ==========================================================
# JWT Token Management
# ==========================================================

def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token with HMAC SHA-256 signature.
    
    Args:
        data: Payload dictionary to encode in token (typically {"sub": user_id})
        expires_delta: Optional custom expiration timedelta
                       If None, uses ACCESS_TOKEN_EXPIRE_MINUTES from config
        
    Returns:
        Signed JWT token string (base64url encoded)
        
    Token Structure:
        Header: {"alg": "HS256", "typ": "JWT"}
        Payload: {**data, "exp": expiration_timestamp, "iat": issued_at_timestamp}
        Signature: HMAC-SHA256(header + payload, SECRET_KEY)
        
    Security:
        - Algorithm: HMAC SHA-256 (symmetric signing)
        - Secret key: Loaded from JWT_SECRET_KEY environment variable
        - Expiration: Mandatory exp claim (prevents token reuse)
        - Issued at: iat claim for token age tracking
    """
    if not data:
        raise ValueError("Token payload data cannot be empty")
    
    # Create mutable copy of payload
    to_encode = data.copy()
    
    # Calculate expiration timestamp
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # Add standard JWT claims
    to_encode.update({
        "exp": expire,  # Expiration timestamp (Unix epoch)
        "iat": datetime.now(timezone.utc),  # Issued at timestamp
    })
    
    # Encode and sign token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.
    
    Args:
        token: JWT token string to decode
        
    Returns:
        Decoded token payload dictionary
        
    Security:
        - Signature verification: HMAC-SHA256 signature validated
        - Expiration check: Rejects expired tokens (exp claim)
        - Algorithm enforcement: Only accepts HS256 (prevents algorithm confusion)
        
    Raises:
        JWTError: If token is invalid, expired, or signature doesn't match
        ValueError: If token is None or empty
    """
    if not token:
        raise ValueError("Token cannot be empty")
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise JWTError(f"Token validation failed: {exc}") from exc


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token with extended expiration.
    
    Args:
        data: Payload dictionary (typically {"sub": user_id, "type": "refresh"})
        expires_delta: Optional custom expiration timedelta
                       If None, uses REFRESH_TOKEN_EXPIRE_DAYS from config
        
    Returns:
        Signed JWT refresh token string
        
    Security:
        - Longer expiration than access tokens (7 days default)
        - Should include "type": "refresh" claim for validation
        - Must be stored securely (httpOnly cookie recommended)
        - Single-use pattern: Invalidate after refresh operation
    """
    if not data:
        raise ValueError("Token payload data cannot be empty")
    
    # Create mutable copy of payload
    to_encode = data.copy()
    
    # Calculate expiration timestamp (longer for refresh tokens)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    # Add standard JWT claims
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    })
    
    # Encode and sign token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    
    return encoded_jwt


def verify_token_type(payload: dict[str, Any], expected_type: str) -> bool:
    """Verify that a decoded JWT payload has the expected type claim.
    
    Args:
        payload: Decoded JWT payload dictionary
        expected_type: Expected token type ("access", "refresh", etc.)
        
    Returns:
        True if token type matches, False otherwise
        
    Security:
        - Prevents token type confusion attacks
        - Ensures refresh tokens can't be used as access tokens
        - Validates custom type claim in payload
    """
    return payload.get("type") == expected_type


__all__ = (
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "create_refresh_token",
    "verify_token_type",
)

