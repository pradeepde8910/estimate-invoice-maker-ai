from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
import base64
import json
import hmac
import hashlib
import time

from v2.database import SessionLocal, get_db
from v2.models.master import User
import config

security = HTTPBearer()

def decode_token(token: str) -> dict:
    """Verifies the HMAC signature and expiry and returns the decoded payload."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_signature = hmac.new(config.JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None

        padding = "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
        payload = json.loads(payload_json)
        if int(time.time()) > payload.get("exp", 0):
            return None
        return payload
    except Exception:
        return None

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> User:
    """Authenticates the user and fetches the user object."""
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired or invalid token")
        
    username = payload.get("user")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
        
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists or is inactive")
        
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
