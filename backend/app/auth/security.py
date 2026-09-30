"""Passwords and session tokens, on the standard library alone.

Passwords use scrypt with a random salt. A session token is a signed claim
(HMAC-SHA256) carrying who the user is and when it expires; nothing is looked
up to check the signature, and tampering with any part invalidates it.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

_N, _R, _P = 2 ** 14, 8, 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(
            password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _sign(body: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())


def create_token(claims: Dict[str, Any], secret: str, ttl_seconds: int) -> str:
    body = _b64(json.dumps({**claims, "exp": int(time.time()) + ttl_seconds}).encode())
    return f"{body}.{_sign(body, secret)}"


def read_token(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """The claims if the signature is good and the token has not expired."""
    try:
        body, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(body, secret)):
            return None
        claims = json.loads(_unb64(body))
        return claims if claims.get("exp", 0) > time.time() else None
    except Exception:
        return None
