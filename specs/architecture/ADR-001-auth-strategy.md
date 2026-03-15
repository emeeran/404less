# ADR-001: Authentication Strategy

## Status

Accepted

## Context

We need to choose an authentication strategy for the application that balances
security, user experience, and implementation complexity.

## Decision

We will use **JWT-based authentication with refresh tokens**.

### Token Strategy

- **Access Token**: JWT, 1-hour expiry, contains user ID and roles
- **Refresh Token**: Opaque token, 7-day expiry, stored hashed in database
- **Algorithm**: RS256 (asymmetric) for token signing

### Session Management

- Multiple concurrent sessions allowed
- Sessions stored in database for revocation capability
- Session metadata includes IP, user agent for security logging

### Password Handling

- Bcrypt hashing with cost factor 12
- Minimum 12 character passwords with complexity requirements
- No password recovery questions (email-based reset only)

## Alternatives Considered

### 1. Session-based (server-side sessions)

**Pros:**
- Easier to revoke
- No token expiry issues

**Cons:**
- Requires sticky sessions or shared session store
- More database load
- Harder to scale horizontally

### 2. Stateless JWT only (no refresh tokens)

**Pros:**
- Simpler implementation
- No database lookups for token validation

**Cons:**
- Cannot revoke tokens before expiry
- Long-lived tokens are a security risk
- Short-lived tokens hurt user experience

### 3. OAuth-only authentication

**Pros:**
- No password management
- Leverages existing trust

**Cons:**
- Requires third-party dependency
- Not all users have social accounts
- More complex initial setup

## Consequences

### Positive

- Stateless access token validation (fast)
- Good balance of security and UX
- Can revoke refresh tokens if compromised
- Scales well horizontally

### Negative

- Need to manage token refresh flow
- Asymmetric keys add complexity
- Database required for refresh token validation

### Risks

- JWT cannot be revoked before expiry - mitigate with short expiry (1 hour)
- Refresh token theft - mitigate with secure/httpOnly cookies or secure storage

## Related Decisions

- ADR-002: Database choice (needed for session storage)
- ADR-003: API gateway strategy

## References

- [RFC 6749 - OAuth 2.0](https://tools.ietf.org/html/rfc6749)
- [RFC 7519 - JSON Web Token](https://tools.ietf.org/html/rfc7519)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
