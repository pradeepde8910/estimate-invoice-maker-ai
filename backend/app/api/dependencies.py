from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models.user import User
from app import config
from app.core.security import decode_access_token, verify_qa_api_key

security = HTTPBearer(auto_error=False)

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db)
) -> User:
    """Authenticates the user and fetches the user object.
    
    Handles both JWT authentication (Bearer token) and QA API Key authentication.
    """
    # 1. Check QA API Key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        if verify_qa_api_key(api_key):
            qa_username = config.QA_TEST_USERNAME
            user = db.query(User).filter(User.username == qa_username).first()
            if user:
                # Optionally, you could attach auth_method to the user object here
                setattr(user, "auth_method", "qa_api_key")
                return user
            
            # Bootstrap fallback for QA API Key
            if qa_username == config.ADMIN_USERNAME:
                bootstrap_user = User(id="bootstrap-admin", username=qa_username, role="Admin")
                setattr(bootstrap_user, "auth_method", "qa_api_key")
                return bootstrap_user
                
            raise HTTPException(status_code=401, detail="QA Account no longer exists or is inactive")
        else:
            raise HTTPException(status_code=401, detail="Invalid API Key or QA mode disabled")

    # 2. Check JWT Credentials
    if credentials is None:
        raise HTTPException(status_code=401, detail="Unauthorized. Please log in.")

    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired or invalid token")
        
    username = payload.get("user")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
        
    user = db.query(User).filter(User.username == username).first()
    if not user:
        # Bootstrap fallback for JWT
        if username == config.ADMIN_USERNAME:
            bootstrap_user = User(id="bootstrap-admin", username=username, role="Admin")
            setattr(bootstrap_user, "auth_method", "jwt")
            return bootstrap_user
        raise HTTPException(status_code=401, detail="Account no longer exists or is inactive")
        
    setattr(user, "auth_method", "jwt")
    return user

def require_roles(*allowed_roles: str):
    """
    Authorization dependency ensuring the user has one of the allowed roles.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Insufficient permissions. Requires one of: {', '.join(allowed_roles)}")
        return current_user
    return role_checker
