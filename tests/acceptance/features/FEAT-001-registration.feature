@spec FEAT-001
Feature: User Registration

  As a new visitor
  I want to create an account with my email and password
  So that I can access protected features of the application

  @spec FEAT-001/AC-001
  Scenario: Successful registration with valid data
    Given I am on the registration page
    And the email "newuser@example.com" is not registered
    When I submit the registration form with:
      | email             | password        | password_confirm |
      | newuser@example.com | SecureP@ss123 | SecureP@ss123    |
    Then the response status should be 201
    And the response should contain "Registration successful"
    And a verification email should be sent to "newuser@example.com"
    And a user with email "newuser@example.com" should exist with email_verified false

  @spec FEAT-001/AC-002
  Scenario: Duplicate email rejection
    Given a user exists with email "existing@example.com"
    When I submit the registration form with:
      | email                | password        | password_confirm |
      | existing@example.com | SecureP@ss123 | SecureP@ss123    |
    Then the response status should be 409
    And the response error should be "email_exists"
    And the message should contain "already exists"

  @spec FEAT-001/AC-003
  Scenario: Password strength validation - too short
    Given I am on the registration page
    When I submit the registration form with:
      | email           | password | password_confirm |
      | test@example.com | Short1!  | Short1!          |
    Then the response status should be 400
    And the response error should be "invalid_input"
    And the password error should contain "at least 12 characters"

  @spec FEAT-001/AC-003
  Scenario: Password strength validation - missing complexity
    Given I am on the registration page
    When I submit the registration form with:
      | email           | password          | password_confirm   |
      | test@example.com | all lowercase123! | all lowercase123!  |
    Then the response status should be 400
    And the password error should contain "uppercase"

  @spec FEAT-001/AC-004
  Scenario: Email verification required before login
    Given a user exists with email "unverified@example.com" and email_verified false
    When I attempt to login with:
      | email                | password      |
      | unverified@example.com | SecureP@ss123 |
    Then the response status should be 403
    And the response error should be "email_not_verified"

  @spec FEAT-001/EC-001
  Scenario: Invalid email format
    Given I am on the registration page
    When I submit the registration form with:
      | email         | password        | password_confirm |
      | invalid-email | SecureP@ss123 | SecureP@ss123    |
    Then the response status should be 400
    And the response error should be "invalid_input"
    And the email error should contain "valid email"

  @spec FEAT-001/EC-002
  Scenario: Passwords do not match
    Given I am on the registration page
    When I submit the registration form with:
      | email           | password        | password_confirm |
      | test@example.com | SecureP@ss123 | DifferentP@ss456 |
    Then the response status should be 400
    And the password_confirm error should contain "do not match"

  @spec FEAT-001/EC-003
  Scenario: Email with leading/trailing whitespace
    Given I am on the registration page
    When I submit the registration form with:
      | email                | password        | password_confirm |
      |  test@example.com  | SecureP@ss123 | SecureP@ss123    |
    Then the response status should be 201
    And the user email should be stored as "test@example.com"

  @spec FEAT-001/EC-005
  Scenario: Very long email
    Given I am on the registration page
    When I submit the registration form with an email longer than 255 characters
    Then the response status should be 400
    And the email error should contain "too long"

  @spec FEAT-001/C-005
  Scenario: Rate limiting - too many attempts
    Given I have made 5 registration attempts from this IP in the last hour
    When I attempt to register again
    Then the response status should be 429
    And the response error should be "rate_limited"
