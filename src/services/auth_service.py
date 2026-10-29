
"""User registration, password verification, and JWT authentication."""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

password_hasher = PasswordHash.recommended()


def register_user(
    conn: sqlite3.Connection,
    full_name: str,
    email: str,
    password: str,
) -> dict:
    """Create a user account and return public user information."""

    full_name = full_name.strip()
    email = email.strip().lower()

    if not full_name:
        raise ValueError("Full name must not be empty")

    if not email:
        raise ValueError("Email must not be empty")

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")

    hashed_password = password_hasher.hash(password)

    try:
        cursor = conn.execute(
            """
            INSERT INTO users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (full_name, email, hashed_password),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        if conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone():
            raise ValueError("An account with this email already exists") from exc
        raise

    return {
        "user_id": cursor.lastrowid,
        "full_name": full_name,
        "email": email,
    }


def authenticate_user(
    conn: sqlite3.Connection,
    email: str,
    password: str,
) -> dict | None:
    """Verify login credentials; return public user information on success."""

    user = conn.execute(
        """
        SELECT user_id, full_name, email, password_hash
        FROM users
        WHERE email = ?
        """,
        (email.strip().lower(),),
    ).fetchone()

    if user is None or not password_hasher.verify(password, user[3]):
        return None

    return {
        "user_id": user[0],
        "full_name": user[1],
        "email": user[2],
    }


def create_access_token(user_id: int) -> str:
    """Create a signed JWT that expires after 30 minutes."""

    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": expires_at,
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    """Validate a JWT and return its user ID."""

    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
    )

    user_id = payload.get("sub")

    if not isinstance(user_id, str) or not user_id.isdigit():
        raise jwt.InvalidTokenError("Invalid user ID in token")

    return int(user_id)
