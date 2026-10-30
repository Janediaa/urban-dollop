
import json
import sqlite3

import pytest
from datetime import date, timedelta

from src.database.models import create_tables
from src.services.insurance_service import (
    assess_service_coverage,
    get_user_policy,
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    create_tables(connection)

    connection.execute(
        """
        INSERT INTO users (full_name, email, password_hash)
        VALUES (?, ?, ?)
        """,
        ("Test User", "test@example.com", "test_hash"),
    )

    connection.execute(
        """
        INSERT INTO insurance_policies (
            user_id,
            policy_number,
            insurer_name,
            plan_name,
            coverage_limit,
            deductible,
            copay_percentage,
            valid_from,
            valid_until,
            covered_services,
            excluded_services
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            "POL-001",
            "Example Health Insurance",
            "Standard Plan",
            500000,
            10000,
            10,
            "2026-01-01",
            "2026-12-31",
            json.dumps(["consultation", "diagnostic tests"]),
            json.dumps(["cosmetic procedures"]),
        ),
    )

    connection.commit()

    yield connection
    connection.close()


def test_get_user_policy_returns_policy_for_owner(conn):
    policy = get_user_policy(conn, user_id=1)

    assert policy is not None
    assert policy["policy_number"] == "POL-001"
    assert policy["insurer_name"] == "Example Health Insurance"
    assert json.loads(policy["covered_services"]) == [
        "consultation",
        "diagnostic tests",
    ]


def test_get_user_policy_does_not_return_another_users_policy(conn):
    policy = get_user_policy(conn, user_id=2)

    assert policy is None


def test_assess_service_coverage_returns_covered_for_listed_service(conn):
    result = assess_service_coverage(
        conn,
        user_id=1,
        service_name="consultation",
    )

    assert result["status"] == "covered"
    assert result["policy_number"] == "POL-001"


def test_assess_service_coverage_returns_excluded_for_excluded_service(conn):
    result = assess_service_coverage(
        conn,
        user_id=1,
        service_name="cosmetic procedures",
    )

    assert result["status"] == "excluded"
    assert result["policy_number"] == "POL-001"


def test_assess_service_coverage_returns_unknown_for_unlisted_service(conn):
    result = assess_service_coverage(
        conn,
        user_id=1,
        service_name="emergency surgery",
    )

    assert result["status"] == "unknown"
    assert result["policy_number"] == "POL-001"


def test_assess_service_coverage_returns_unknown_without_a_policy(conn):
    result = assess_service_coverage(
        conn,
        user_id=2,
        service_name="consultation",
    )

    assert result["status"] == "unknown"
    assert result["policy_number"] is None


from datetime import date, timedelta


def test_expired_policy_does_not_return_covered(conn):
    conn.execute(
        "UPDATE insurance_policies SET valid_until = ? WHERE user_id = ?",
        ((date.today() - timedelta(days=1)).isoformat(), 1),
    )
    conn.commit()

    result = assess_service_coverage(
        conn, user_id=1, service_name="consultation"
    )

    assert result["status"] == "expired"
    assert result["policy_number"] == "POL-001"


def test_future_policy_does_not_return_covered(conn):
    conn.execute(
        "UPDATE insurance_policies SET valid_from = ? WHERE user_id = ?",
        ((date.today() + timedelta(days=1)).isoformat(), 1),
    )
    conn.commit()

    result = assess_service_coverage(
        conn, user_id=1, service_name="consultation"
    )

    assert result["status"] == "not_yet_valid"
    assert result["policy_number"] == "POL-001"


def test_policy_valid_today_can_return_covered(conn):
    today = date.today().isoformat()
    conn.execute(
        """
        UPDATE insurance_policies
        SET valid_from = ?, valid_until = ?
        WHERE user_id = ?
        """,
        (today, today, 1),
    )
    conn.commit()

    result = assess_service_coverage(
        conn, user_id=1, service_name="consultation"
    )

    assert result["status"] == "covered"


def test_invalid_policy_date_returns_unknown(conn):
    conn.execute(
        "UPDATE insurance_policies SET valid_until = ? WHERE user_id = ?",
        ("not-a-date", 1),
    )
    conn.commit()

    result = assess_service_coverage(
        conn, user_id=1, service_name="consultation"
    )

    assert result["status"] == "unknown"
    assert result["policy_number"] == "POL-001"


def test_get_user_policy_returns_financial_details(conn):
    policy = get_user_policy(conn, user_id=1)

    assert policy["coverage_limit"] == 500000
    assert policy["deductible"] == 10000
    assert policy["copay_percentage"] == 10


@pytest.mark.parametrize(
    ("column", "invalid_value"),
    [
        ("coverage_limit", -1),
        ("deductible", -1),
        ("copay_percentage", -1),
        ("copay_percentage", 101),
    ],
)
def test_invalid_financial_policy_values_return_unknown(
    conn, column, invalid_value
):
    # Column names are restricted to this explicit test list.
    conn.execute(
        f"UPDATE insurance_policies SET {column} = ? WHERE user_id = ?",
        (invalid_value, 1),
    )
    conn.commit()

    result = assess_service_coverage(
        conn, user_id=1, service_name="consultation"
    )

    assert result["status"] == "unknown"
    assert result["policy_number"] == "POL-001"
    assert "financial" in result["message"].lower()

