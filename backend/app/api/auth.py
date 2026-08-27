from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
import time
import base64
import json
import hmac
import hashlib
from typing import Optional

from app.database import get_db
from app.models.master import User
from v1.utils.security import verify_password
from v1.utils.rate_limiter import check_login_rate_limit, record_login_failure, record_login_success
from app import config

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

def create_token(username: str, role: str) -> str:
    # Token valid for 24 hours
    exp = int(time.time()) + 86400
    payload = {"user": username, "role": role, "exp": exp}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(config.JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

@router.post("/login")
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    # Brute-force guard: v1/utils/rate_limiter.py already implemented this
    # (5 failed attempts / 15 min -> 15 min lockout, keyed by IP+username)
    # but was never wired into the endpoint that's actually mounted at
    # /api/auth/login, leaving login completely unthrottled.
    client_ip = http_request.client.host if http_request.client else "unknown"
    locked_seconds = check_login_rate_limit(client_ip, request.username)
    if locked_seconds is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {int(locked_seconds) // 60 + 1} minute(s).",
        )

    user = db.query(User).filter(User.username == request.username).first()

    # Bootstrap-only fallback: lets an operator log in as the configured
    # admin before any User row exists. Disabled entirely if ADMIN_PASSWORD
    # isn't set - no hardcoded default credential exists.
    if not user and db.query(User).count() == 0:
        if (
            config.ADMIN_PASSWORD
            and request.username == config.ADMIN_USERNAME
            and hmac.compare_digest(request.password.encode("utf-8"), config.ADMIN_PASSWORD.encode("utf-8"))
        ):
            record_login_success(client_ip, request.username)
            token = create_token(request.username, "Admin")
            return {"token": token, "role": "Admin"}

    if not user or not verify_password(request.password, user.password_hash):
        record_login_failure(client_ip, request.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    record_login_success(client_ip, request.username)
    token = create_token(user.username, user.role)
    return {"token": token, "role": user.role}

@router.get("/validate")
def validate():
    return {"status": "valid"}
