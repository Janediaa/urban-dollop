
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.database.models import create_tables
from src.services.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    decode_access_token,
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    create_tables(connection)
    yield connection
    connection.close()


def test_register_user_stores_hashed_password(conn):
    user = register_user(
        conn, "Test Patient", "patient@example.com", "securepass123"
    )

    stored = conn.execute(
        "SELECT password_hash FROM users WHERE user_id = ?",
        (user["user_id"],),
    ).fetchone()

    assert user["email"] == "patient@example.com"
    assert stored[0] != "securepass123"
    assert authenticate_user(
        conn, "patient@example.com", "securepass123"
    )["user_id"] == user["user_id"]


def test_email_is_normalized(conn):
    user = register_user(
        conn, "Test Patient", "  PATIENT@Example.com  ", "securepass123"
    )

    assert user["email"] == "patient@example.com"
    assert authenticate_user(
        conn, "PATIENT@EXAMPLE.COM", "securepass123"
    ) is not None


def test_duplicate_email_is_rejected(conn):
    register_user(conn, "First Patient", "patient@example.com", "securepass123")

    with pytest.raises(ValueError, match="already exists"):
        register_user(
            conn, "Second Patient", "PATIENT@example.com", "securepass456"
        )


def test_short_password_is_rejected(conn):
    with pytest.raises(ValueError, match="at least 8 characters"):
        register_user(conn, "Test Patient", "patient@example.com", "short")


def test_wrong_password_is_rejected(conn):
    register_user(conn, "Test Patient", "patient@example.com", "securepass123")

    assert authenticate_user(
        conn, "patient@example.com", "wrongpassword"
    ) is None


def test_unknown_email_is_rejected(conn):
    assert authenticate_user(
        conn, "unknown@example.com", "securepass123"
    ) is None


def test_access_token_round_trip(conn):
    user = register_user(
        conn, "Test Patient", "patient@example.com", "securepass123"
    )

    token = create_access_token(user["user_id"])

    assert decode_access_token(token) == user["user_id"]


def test_expired_token_is_rejected():
    from src.services.auth_service import JWT_ALGORITHM, JWT_SECRET_KEY

    expired_token = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_invalid_token_is_rejected():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("this-is-not-a-valid-token")
