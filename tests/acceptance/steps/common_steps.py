"""
Common step definitions for acceptance tests.

Shared across all features.
"""

import pytest
from pytest_bdd import given, when, then, parsers

# These would connect to your actual test fixtures
# from tests.fixtures import api_client, db_session


@given("I am on the registration page")
def on_registration_page():
    """Navigate to registration page (for UI tests)."""
    pass


@given("I am on the login page")
def on_login_page():
    """Navigate to login page (for UI tests)."""
    pass


@given(parsers.parse('the email "{email}" is not registered'))
def email_not_registered(email):
    """Ensure email is not in database."""
    # await db_session.execute("DELETE FROM users WHERE email = ?", email)
    pass


@given(parsers.parse('a user exists with email "{email}"'))
def user_exists(email):
    """Create a user with given email."""
    # await create_test_user(email=email)
    pass


@given(parsers.parse('a user exists with email "{email}" and email_verified {status}'))
def user_exists_with_verification(email, status):
    """Create a user with specific verification status."""
    # verified = status.lower() == "true"
    # await create_test_user(email=email, email_verified=verified)
    pass


@given(parsers.parse("I have made {count:d} registration attempts from this IP in the last hour"))
def rate_limit_setup(count):
    """Setup rate limit scenario."""
    # for _ in range(count):
    #     await record_registration_attempt(ip="test-ip")
    pass


@when(parsers.parse("I submit the registration form with:\n{table}"))
def submit_registration(table):
    """Submit registration form with table data."""
    # Parse table and make API request
    pass


@when(parsers.parse("I attempt to login with:\n{table}"))
def attempt_login(table):
    """Attempt login with table data."""
    pass


@when(parsers.parse("I submit the registration form with an email longer than {length:d} characters"))
def submit_long_email(length):
    """Submit form with very long email."""
    # long_email = "a" * (length + 1) + "@example.com"
    # await api_client.post("/auth/register", json={"email": long_email, ...})
    pass


@when("I attempt to register again")
def attempt_register_again():
    """Make another registration attempt."""
    pass


@then(parsers.parse("the response status should be {status:d}"))
def check_status(status):
    """Verify response status code."""
    # assert response.status_code == status
    pass


@then(parsers.parse('the response should contain "{text}"'))
def response_contains(text):
    """Verify response contains text."""
    # assert text in response.text
    pass


@then(parsers.parse('the response error should be "{error}"'))
def check_error_code(error):
    """Verify error code in response."""
    # assert response.json()["error"] == error
    pass


@then(parsers.parse('the message should contain "{text}"'))
def message_contains(text):
    """Verify message contains text."""
    # assert text in response.json()["message"]
    pass


@then(parsers.parse('a verification email should be sent to "{email}"'))
def verification_email_sent(email):
    """Verify email was sent."""
    # assert email in mock_email_service.sent_emails
    pass


@then(parsers.parse('a user with email "{email}" should exist with email_verified {status}'))
def verify_user_state(email, status):
    """Verify user exists with correct state."""
    # user = await get_user_by_email(email)
    # assert user is not None
    # assert user.email_verified == (status.lower() == "true")
    pass


@then(parsers.parse('the user email should be stored as "{email}"'))
def verify_stored_email(email):
    """Verify email was trimmed before storage."""
    # user = await get_last_created_user()
    # assert user.email == email
    pass


@then(parsers.parse('the {field} error should contain "{text}"'))
def field_error_contains(field, text):
    """Verify specific field error message."""
    # details = response.json().get("details", [])
    # field_errors = [d for d in details if d["field"] == field]
    # assert any(text in e["message"] for e in field_errors)
    pass
