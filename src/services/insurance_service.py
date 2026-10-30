"""Service functions for retrieving a user's insurance policy."""

import json
from datetime import date
import math

def get_user_policy(conn, user_id):
    """Return a user's insurance policy, or None if not found."""

    if isinstance(user_id, bool) or not isinstance(user_id, int):
        raise TypeError("user_id must be an integer.")

    if user_id <= 0:
        raise ValueError("user_id must be positive.")

    cursor = conn.execute(
        """
        SELECT
            policy_id,
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
        FROM insurance_policies
        WHERE user_id = ?
        ORDER BY policy_id DESC
        LIMIT 1
        """,
        (user_id,),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))




def assess_service_coverage(conn, user_id, service_name):
    """Assess coverage using only the services recorded in a user's policy."""

    if not isinstance(service_name, str):
        raise TypeError("service_name must be a string.")

    service_name = service_name.strip()

    if not service_name:
        raise ValueError("service_name cannot be empty.")

    policy = get_user_policy(conn, user_id)

    if policy is None:
        return {
            "status": "unknown",
            "policy_number": None,
            "message": (
                "No stored insurance policy was found. "
                "Coverage cannot be determined."
            ),
        }
        # Validate policy dates before assessing service coverage.
    try:
        valid_from = date.fromisoformat(policy["valid_from"])
        valid_until = date.fromisoformat(policy["valid_until"])
        today = date.today()
    except (ValueError, TypeError):
        return {
            "status": "unknown",
            "policy_number": policy["policy_number"],
            "message": (
                "The policy validity dates are missing or invalid. "
                "Coverage cannot be determined."
            ),
        }

    if valid_until < valid_from:
        return {
            "status": "unknown",
            "policy_number": policy["policy_number"],
            "message": (
                "The policy validity period is invalid. "
                "Coverage cannot be determined."
            ),
        }

    if today < valid_from:
        return {
            "status": "not_yet_valid",
            "policy_number": policy["policy_number"],
            "message": "This policy's validity period has not started yet.",
        }

    if today > valid_until:
        return {
            "status": "expired",
            "policy_number": policy["policy_number"],
            "message": "This policy's validity period has ended.",
        }

    
    # Validate financial values when they are provided.
    financial_fields = (
        ("coverage_limit", policy["coverage_limit"], 0, None),
        ("deductible", policy["deductible"], 0, None),
        ("copay_percentage", policy["copay_percentage"], 0, 100),
    )

    for field_name, value, minimum, maximum in financial_fields:
        if value is None:
            continue

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < minimum
            or (maximum is not None and value > maximum)
        ):
            return {
                "status": "unknown",
                "policy_number": policy["policy_number"],
                "message": (
                    f"The stored financial value '{field_name}' is invalid. "
                    "Coverage cannot be determined."
                ),
            }


    try:
        covered_services = json.loads(policy["covered_services"])
        excluded_services = json.loads(policy["excluded_services"])
    except (json.JSONDecodeError, TypeError):
        return {
            "status": "unknown",
            "policy_number": policy["policy_number"],
            "message": (
                "The stored service lists could not be interpreted. "
                "Coverage cannot be determined."
            ),
        }

    if not isinstance(covered_services, list) or not isinstance(
        excluded_services, list
    ):
        return {
            "status": "unknown",
            "policy_number": policy["policy_number"],
            "message": "The stored policy data is invalid. Coverage cannot be determined.",
        }

    normalized_service = service_name.casefold()

    covered = any(
        isinstance(item, str) and item.strip().casefold() == normalized_service
        for item in covered_services
    )
    excluded = any(
        isinstance(item, str) and item.strip().casefold() == normalized_service
        for item in excluded_services
    )

    if excluded:
        status = "excluded"
        message = "This service is listed among the policy's exclusions."
    elif covered:
        status = "covered"
        message = (
            "This service is listed among the policy's covered services. "
            "Actual benefits and reimbursement are not guaranteed."
        )
    else:
        status = "unknown"
        message = (
            "This service is not explicitly listed as covered or excluded. "
            "Check the policy wording or contact the insurer."
        )

    return {
        "status": status,
        "policy_number": policy["policy_number"],
        "message": message,
    }
