
from typing import Optional
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.user import User
from app.services.supabase_client import supabase_client

logger = logging.getLogger(__name__)
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Verify token using Supabase and return user."""
    logger.info("[AUTH] ========== Authentication Start ==========")
    token = credentials.credentials
    logger.info(f"[AUTH] Received token (first 20 chars): {token[:20]}...")

    try:
        # Use Supabase's built-in token verification (handles ES256/HS256 automatically)
        logger.info(f"[AUTH] Verifying token with Supabase...")
        response = supabase_client.client.auth.get_user(token)

        if not response.user:
            logger.error(f"[AUTH] Token verification failed - no user returned")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )

        logger.info(f"[AUTH] Token verified. User: {response.user.email}")
        user = User(
            id=response.user.id,
            email=response.user.email,
            created_at=response.user.created_at,
            email_confirmed_at=response.user.email_confirmed_at,
            last_sign_in_at=response.user.last_sign_in_at,
            token=token
        )

        logger.info(f"[AUTH] ========== Authentication Success: {user.email} ==========")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AUTH] Token verification FAILED: {str(e)}")
        logger.error(f"[AUTH] Token (first 50 chars): {token[:50]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )