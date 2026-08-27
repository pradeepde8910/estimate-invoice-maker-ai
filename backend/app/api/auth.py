from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.core.rate_limiter import check_login_rate_limit, record_login_failure, record_login_success
from app import config

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    # Brute-force guard: v1/utils/rate_limiter.py already implemented this
    # (5 failed attempts / 15 min -> 15 min lockout, keyed by IP+username)
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
            # Note: verify_password also supports constant-time compare for plaintext
            and verify_password(request.password, config.ADMIN_PASSWORD)
        ):
            record_login_success(client_ip, request.username)
            token = create_access_token(request.username, "Admin")
            return {"token": token, "role": "Admin"}

    if not user or not verify_password(request.password, user.password_hash):
        record_login_failure(client_ip, request.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    record_login_success(client_ip, request.username)
    token = create_access_token(user.username, user.role)
    return {"token": token, "role": user.role}

@router.get("/validate")
def validate():
    return {"status": "valid"}
