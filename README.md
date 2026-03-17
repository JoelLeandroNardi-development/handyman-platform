# Smart Handyman Marketplace - Microservices Backend

This repository contains the backend for a handyman marketplace platform built with FastAPI microservices, PostgreSQL, Redis, and RabbitMQ.

This README is the single source of truth for project testing and CI usage. It consolidates the former content from:
- tests/README.md
- TESTING_DELIVERY.md
- TESTING_QUICKREF.md

## Current Status

- Test result baseline: 217 passed
- Combined coverage baseline: 96% over shared and services targets
- CI workflow: active in .github/workflows/tests.yml for Python 3.11 and 3.12
- Core testing tracks: unit, integration, and failure-mode

## Platform Architecture

High-level service roles:
- gateway-service: API facade, RBAC, routing helpers, circuit breakers
- auth-service: authentication and token-oriented flows
- user-service: user domain persistence and event publishing
- handyman-service: handyman domain persistence and event publishing
- booking-service: booking lifecycle persistence and outbox publishing
- availability-service: slot and reservation state with Redis-backed workflows
- match-service: matching, projections, caching, and ranking-related logic
- search-service: search endpoint service
- shared package: cross-service utilities and shared schemas

Core principles used across services:
- Outbox pattern for reliable event publishing
- Event-driven integration over RabbitMQ
- Idempotent consumers
- Background workers for outbox and expiry handling

## Testing Layout

Current test structure:

```text
tests/
  unit/
    test_consumer.py
    test_gateway_helpers.py
    test_idempotency.py
    test_intervals.py
    test_match_services.py
    test_mq.py
    test_outbox_worker.py
    test_reservations.py
    test_schemas.py
    test_shared_helpers.py
    test_shared_models.py
    conftest.py
  integration/
    test_booking_lifecycle.py
    conftest.py
  failure_mode/
    test_consumer_failures.py
    conftest.py
```

Supporting test/config files:
- pytest.ini
- conftest.py
- requirements-test.txt
- Makefile
- run_tests.py
- .github/workflows/tests.yml

## What The Test Suite Covers

Unit coverage includes:
- Interval overlap and containment logic
- Redis idempotency behavior
- RabbitMQ consumer topology/retry/DLQ behavior
- Shared event, role, DB, and CRUD helper behavior
- Outbox worker claim/send/failure/retry loops
- Match service helper and projection/caching flows
- Availability reservation key and state helpers
- Gateway RBAC and circuit-breaker behavior
- Shared schema validation across auth, users, handymen, bookings, availability, and match domains

Integration coverage includes:
- Booking lifecycle transitions and event-driven progression

Failure-mode coverage includes:
- Retry and DLQ scenarios
- Malformed payload handling
- Consumer error path behavior

## Quick Start

### 1) Install test dependencies

```bash
pip install -r requirements-test.txt
```

Optional shared editable install (recommended for local development):

```bash
cd shared
pip install -e ".[test]"
cd ..
```

Install runtime dependencies for each service when running cross-service local flows:

```bash
pip install -r services/auth-service/requirements.txt
pip install -r services/availability-service/requirements.txt
pip install -r services/booking-service/requirements.txt
pip install -r services/gateway-service/requirements.txt
pip install -r services/handyman-service/requirements.txt
pip install -r services/match-service/requirements.txt
pip install -r services/user-service/requirements.txt
```

### 2) Run tests

All tests:

```bash
pytest tests/ -v
```

By category:

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/failure_mode/ -v
```

By marker:

```bash
pytest -m unit
pytest -m integration
pytest -m failure_mode
pytest -m intervals
pytest -m idempotency
pytest -m rabbit
pytest -m booking_lifecycle
```

Coverage:

```bash
pytest tests --cov=shared --cov=services --cov-report=term-missing --cov-report=xml
python -m coverage report
python -m coverage html
```

If using helper commands:

```bash
make test
make test-unit
make test-integration
make test-failure
make test-cov-html
python run_tests.py all
```

### 3) Run a specific test target

```bash
pytest tests/unit/test_intervals.py
pytest tests/unit/test_intervals.py::TestOverlaps
pytest tests/unit/test_intervals.py::TestOverlaps::test_overlaps_partial_overlap
pytest -vv -s
pytest --durations=10
```

## CI Pipeline

Workflow file:
- .github/workflows/tests.yml

Trigger conditions:
- Push to main or develop
- Pull requests to main or develop

Matrix:
- Python 3.11
- Python 3.12

Service containers in CI:
- PostgreSQL
- RabbitMQ
- Redis

Main CI steps:
1. Checkout and Python setup
2. Install root test dependencies from requirements-test.txt
3. Install shared module
4. Install per-service runtime dependencies
5. Lint step (non-blocking)
6. Unit tests with coverage
7. Integration tests with coverage append
8. Failure-mode tests
9. Codecov upload
10. Coverage report and HTML artifact upload

## Recent CI and Dependency Fixes

The current pipeline includes the latest fixes that were needed to stabilize GitHub Actions:

1. GitHub Action version upgrades
- actions/checkout moved to v5
- actions/setup-python moved to v5
- actions/upload-artifact moved to v4
- codecov/codecov-action moved to v5

2. Node runtime compatibility
- FORCE_JAVASCRIPT_ACTIONS_TO_NODE24 is set in workflow env

3. Coverage command reliability
- coverage is invoked as python -m coverage to avoid shell path issues

4. Dependency conflict prevention
- Invalid unittest-mock pin was removed from requirements-test.txt
- Service requirements were cleaned to runtime-only dependencies
- Test-only dependencies are centralized in root requirements-test.txt

5. Shared package import stability in CI
- PYTHONPATH is set to repository root only
- This avoids package shadowing and fixes shared.shared import resolution

## Test Dependency Policy

To avoid resolver conflicts and duplicate pins:
- Keep test tool dependencies in requirements-test.txt
- Keep service requirements.txt files runtime-only
- Prefer one central test dependency source for CI

## Fixtures and Mocks

Common fixtures used by test suites include:
- redis_mock
- rabbit_channel_mock
- rabbit_message_mock
- sample_booking_data
- sample_event
- sample_intervals

Shared fixture modules:
- conftest.py at repository root
- tests/unit/conftest.py
- tests/integration/conftest.py
- tests/failure_mode/conftest.py

## Markers

Registered markers in pytest.ini:
- unit
- integration
- failure_mode
- rabbit
- idempotency
- intervals
- booking_lifecycle
- slow
- asyncio

## Troubleshooting

ModuleNotFoundError for pytest:

```bash
pip install pytest pytest-asyncio
```

ModuleNotFoundError for shared.shared in CI or local runs:
- Ensure PYTHONPATH points to repository root
- Do not prepend only the shared subdirectory as top-level PYTHONPATH

Linux/macOS example:

```bash
export PYTHONPATH="$(pwd)"
```

Windows PowerShell example:

```powershell
$env:PYTHONPATH = (Get-Location).Path
```

Dependency resolution conflict (multiple versions of same package):
- Check duplicate pins across requirements files
- Keep test pins only in requirements-test.txt
- Keep service requirements runtime-only

Coverage command not found:

```bash
python -m coverage report
python -m coverage html
```

## Delivery Summary

Completed outcomes:
- Comprehensive unit, integration, and failure-mode test suite
- High coverage for shared and service-critical logic
- CI workflow with matrix execution and coverage artifacts
- Stabilized dependency installation process in CI
- Updated workflow for current GitHub Actions runtime requirements

Quality baseline achieved in this solution:
- Passing test suite at 217 tests
- Coverage baseline at 96%

## Development Notes

- Keep tests behavior-focused rather than placeholder assertions
- Add new tests with marker annotations to maintain suite organization
- Prefer shared helpers and schemas for consistency across services
- Maintain CI parity with local commands where possible

## Useful Commands Cheat Sheet

```bash
# Full suite with coverage
pytest tests --cov=shared --cov=services --cov-report=term-missing

# Unit only
pytest tests/unit/ -v

# Integration only
pytest tests/integration/ -v

# Failure only
pytest tests/failure_mode/ -v

# Marker subset
pytest -m "unit and not slow"

# HTML coverage
python -m coverage html
```

This README is intentionally centralized so contributors can onboard, run tests, debug CI, and extend coverage without switching between multiple testing documents.
