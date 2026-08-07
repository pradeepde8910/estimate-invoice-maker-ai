"""Small shared helper for building forged-but-validly-signed tokens in tests."""
import base64
import hashlib
import hmac
import json
import time

import config


def forge_token(username: str, secret: str = None, exp_delta: int = 86400) -> str:
    secret = secret if secret is not None else config.JWT_SECRET
    payload = {"user": username, "exp": int(time.time()) + exp_delta}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def headers_for(username: str) -> dict:
    return {"Authorization": f"Bearer {forge_token(username)}"}


def post_as(client, username: str, url: str, **kwargs):
    kwargs_headers = kwargs.pop("headers", {})
    return client.post(url, headers={**headers_for(username), **kwargs_headers}, **kwargs)
