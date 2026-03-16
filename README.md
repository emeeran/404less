# SDD Template

A starter project template for Spec-Driven Development (SDD).

## Quick Start

```bash
# Install dependencies
make install

# Start development server
make dev

# Run tests
make test

# Run SDD checks
make sdd-check
```

## Project Structure

```
sdd-template/
├── specs/              # Feature specifications (single source of truth)
│   ├── features/       # Feature specs (FEAT-XXX.yaml)
│   ├── domain/         # Domain models
│   ├── api/            # API contracts (OpenAPI)
│   └── architecture/   # ADRs and diagrams
│
├── contracts/          # Generated data contracts
│   ├── schemas/        # JSON Schema
│   ├── python/         # Pydantic models
│   └── typescript/     # TypeScript types
│
├── src/                # Implementation code
│   └── auth/           # Auth feature (FEAT-001, FEAT-002, FEAT-003)
│
├── tests/              # Test files
│   ├── acceptance/     # Gherkin/BDD tests
│   ├── unit/           # Unit tests
│   └── integration/    # Integration tests
│
├── docs/               # Generated documentation
├── migrations/         # Database migrations
├── stubs/              # Interface stubs
└── .sdd/               # SDD tooling config
```

## SDD Workflow

### 1. Write Spec
```bash
# Create new spec from template
cp specs/features/_template.yaml specs/features/FEAT-XXX-my-feature.yaml
```

### 2. Validate Spec
```bash
make spec-lint
```

### 3. Generate Artifacts
```bash
make generate-contracts  # Generate data contracts
make generate-scaffold   # Generate code scaffold
make generate-tests      # Generate tests
```

### 4. Implement

Write implementation code with spec annotations to maintain traceability.

**Steps:**
1. Reference the spec for your feature (`specs/features/FEAT-XXX.yaml`)
2. Write failing tests first (TDD approach)
3. Implement with spec annotations in docstrings
4. Verify tests pass and cover all acceptance criteria

**Annotation Patterns:**

| Annotation | Scope | Example |
|------------|-------|---------|
| `@spec FEAT-XXX` | Module/Class | Links file to feature |
| `@spec FEAT-XXX/AC-XXX` | Function | Links to acceptance criterion |
| `@spec FEAT-XXX/EC-XXX` | Function | Links to edge case |
| `@spec FEAT-XXX/C-XXX` | Function | Links to constraint |

**Example:**

```python
"""
User Registration Service

@spec FEAT-001
@acceptance_criteria AC-001, AC-002, AC-003
"""

async def register_user(email: str, password: str) -> User:
    """
    Register a new user.

    @spec FEAT-001/AC-001 - Successful registration
    @spec FEAT-001/EC-001 - Invalid email format
    @spec FEAT-001/C-001 - Password minimum 12 characters
    """
    validate_email(email)  # @spec FEAT-001/EC-001
    validate_password(password)  # @spec FEAT-001/C-001
    return await create_user(email, password)
```

**Best Practices:**
- Every public function should have a `@spec` annotation
- Use full paths: `FEAT-XXX/AC-XXX` not just `AC-XXX`
- Group related criteria: `@acceptance_criteria AC-001, AC-002`
- Run `make spec-compliance` to verify annotations match implementation

### 5. Test & Validate
```bash
make test
make spec-coverage      # Check coverage
make spec-compliance    # Check implementation matches spec
```

### 6. Commit
```bash
make commit  # Guided commit with spec references
```

## Available Commands

| Command | Description |
|---------|-------------|
| `make spec-lint` | Lint all specs |
| `make spec-coverage` | Check spec-to-test coverage |
| `make spec-compliance` | Check implementation compliance |
| `make spec-drift` | Detect spec drift |
| `make sdd-check` | Run all SDD checks |
| `make generate-contracts` | Generate data contracts |
| `make generate-docs` | Generate documentation |
| `make generate-scaffold` | Generate code scaffold |
| `make test` | Run all tests |
| `make commit` | Guided commit |

## Spec Template

```yaml
spec:
  id: FEAT-XXX
  name: Feature Name
  version: 1.0.0
  status: draft

  acceptance_criteria:
    - id: AC-001
      given: Context
      when: Action
      then: Expected result

  edge_cases:
    - id: EC-001
      scenario: Edge case description
      expected: Expected behavior

  constraints:
    - id: C-001
      type: security
      description: Constraint description
```

## Code Annotations

Link code to specs using annotations:

```python
# @spec FEAT-001/AC-001
# @acceptance_criteria AC-001, AC-002
# @edge_cases EC-001, EC-002
async def register_user(email: str, password: str):
    """@spec FEAT-001/AC-001"""
    pass
```

## CI/CD

The `.github/workflows/sdd-checks.yaml` pipeline runs:
1. Spec linting
2. Spec coverage check
3. Test execution
4. Compliance check
5. Security scan

## Documentation

- [SDD Workflow Guide](../spec_workflow.md)
- [Spec Index](specs/index.yaml)
- [Coverage Matrix](.sdd/coverage-matrix.yaml)

## Architecture

### Core Modules

| Module | Purpose |
|--------|---------|
| `src/shared/config.py` | Centralized configuration constants |
| `src/shared/decorators.py` | Error handling decorators for routes |
| `src/shared/db/connection.py` | Database session management |
| `src/shared/email/template_engine.py` | Abstract template rendering |
| `src/scanner/crawler_registry.py` | Crawler dependency injection |
| `src/scanner/error_handlers.py` | HTTP error classification |

### Design Patterns

- **Registry Pattern**: `CrawlerRegistry` for injectable crawler management
- **Decorator Pattern**: `@handle_service_errors` for route error handling
- **Strategy Pattern**: `TemplateEngine` abstraction for email templates
- **Context Manager**: `get_background_session()` for database sessions

### Configuration

Environment variables (see `src/shared/config.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `CRAWLER_MAX_CONCURRENT` | 5 | Max concurrent requests |
| `CRAWLER_MIN_DELAY` | 0.1 | Min delay between requests (seconds) |
| `CRAWLER_TIMEOUT` | 30 | HTTP timeout (seconds) |
| `CRAWLER_MAX_REDIRECTS` | 10 | Max redirect hops |
| `CRAWLER_MAX_DEPTH` | 10 | Max crawl depth |

### Frontend Architecture

The frontend (`static/app.js`) is a single-page application using:
- Server-Sent Events (SSE) for real-time updates
- Native browser APIs (no framework dependencies)
- Modular structure under `static/modules/`
