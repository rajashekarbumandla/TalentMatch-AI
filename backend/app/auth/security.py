"""
Password hashing and login tokens.

Passwords
---------
Passwords are NEVER stored. We store a *hash* made with scrypt (Python standard library):
    scrypt(password, salt) -> 64 bytes
- The salt is 16 random bytes per user, so two users with the same password get
  different hashes and pre-computed "rainbow tables" are useless.
- scrypt is deliberately slow and memory-hungry (n=2^14, r=8), which makes guessing
  millions of passwords from a stolen database impractical.
- Verification re-computes the hash and compares in constant time (hmac.compare_digest),
  so response timing leaks nothing.
Stored format:  scrypt$16384$8$1$<salt base64>$<hash base64>

Tokens
------
After a successful login the API returns a JWT (JSON Web Token) signed with HS256
using JWT_SECRET_KEY. It contains the user id ("sub"), an expiry ("exp") and the
user's token_version ("ver"). The browser sends it as "Authorization: Bearer <token>".
Changing a password or disabling an account increments token_version, which
immediately invalidates every token issued before.
"""
import base64
import hashlib
import hmac
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

logger = logging.getLogger(__name__)

SCRYPT_N, SCRYPT_R, SCRYPT_P, KEY_LENGTH = 2**14, 8, 1, 64
ALGORITHM = "HS256"

if not settings.JWT_SECRET_KEY:
    settings.JWT_SECRET_KEY = secrets.token_urlsafe(48)
    logger.warning("JWT_SECRET_KEY is not set; using a temporary key. Everyone will be logged out when the API restarts.")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_LENGTH)
    encode = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encode(salt)}${encode(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, digest_b64 = stored_hash.split("$")
        if algorithm != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(digest_b64)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# A fixed dummy hash: when an email doesn't exist we still run one scrypt check, so a
# login attempt takes the same time whether or not the account exists.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def password_problem(password: str) -> str | None:
    """Simple strength rules; returns a message, or None if the password is acceptable."""
    if len(password) < settings.MIN_PASSWORD_LENGTH:
        return f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters."
    if len(password) > 128:
        return "Password must be at most 128 characters."
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return "Password must contain at least one letter and one number."
    return None


def create_access_token(user_id: uuid.UUID, token_version: int) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "ver": token_version, "exp": expires_at, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM), expires_at


def decode_access_token(token: str) -> dict | None:
    """The token's claims, or None if it is invalid, tampered with or expired."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["sub", "exp", "ver"]})
    except jwt.PyJWTError:
        return None
