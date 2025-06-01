from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
from services.firebase_auth_service import FirebaseAuthService
import logging

logger = logging.getLogger(__name__)

# Initialize Firebase Auth Service
firebase_auth = FirebaseAuthService()

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user from Firebase ID token
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        User information from Firebase
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract the token
    token = credentials.credentials
    
    # Verify the token with Firebase
    user_info = await firebase_auth.verify_id_token(token)
    
    return user_info

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Optional dependency to get current user (doesn't raise error if not authenticated)
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        User information from Firebase or None if not authenticated
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        user_info = await firebase_auth.verify_id_token(token)
        return user_info
    except HTTPException:
        # Log the error but don't raise it
        logger.warning("Optional authentication failed")
        return None

async def get_user_uid(current_user: Dict[str, Any] = Depends(get_current_user)) -> str:
    """
    Dependency to get just the user UID
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User UID string
    """
    return current_user["uid"]

async def require_verified_email(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dependency that requires user to have verified email
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User information
        
    Raises:
        HTTPException: If email is not verified
    """
    if not current_user.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    return current_user
