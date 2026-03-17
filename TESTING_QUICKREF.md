# 🧪 Testing Quick Reference Card

## One-Time Setup
```bash
# Install test dependencies
pip install -r requirements-test.txt

# Optional: for all services
pip install -r services/*/requirements.txt
```

## Run Tests

### All Tests
```bash
# Option 1: Make
make test

# Option 2: Python script  
python run_tests.py all

# Option 3: Direct
pytest tests/ -v
```

### By Category
```bash
make test-unit           # Unit tests
make test-integration    # Integration tests
make test-failure        # Failure-mode tests
```

### By Feature (Markers)
```bash
pytest -m intervals       # Interval overlap
pytest -m idempotency     # Event deduplication
pytest -m rabbit          # RabbitMQ consumer
pytest -m booking         # Booking lifecycle
```

### With Coverage
```bash
make test-cov-html       # Generate HTML report
pytest --cov=shared --cov=services --cov-report=term
```

### Watch Mode
```bash
pytest-watch
# Or: ptw
```

---

## File Locations

| Type | Location |
|------|----------|
| Unit Tests | `tests/unit/` |
| Integration Tests | `tests/integration/` |
| Failure Tests | `tests/failure_mode/` |
| Test Guide | `tests/README.md` |
| Full Docs | `TESTING.md` |
| CI/CD Config | `.github/workflows/tests.yml` |

---

## Test Coverage

- **Intervals:** 14 tests coverage overlap detection
- **Idempotency:** 12 tests for event deduplication
- **Consumer:** 20 tests for RabbitMQ reliability
- **Booking:** 15 integration tests for complete flow
- **Failures:** 30+ resilience tests

**Total:** 112+ test cases

---

## Run Specific Test

```bash
# Specific file
pytest tests/unit/test_intervals.py

# Specific class
pytest tests/unit/test_intervals.py::TestOverlaps

# Specific test
pytest tests/unit/test_intervals.py::TestOverlaps::test_overlaps_partial_overlap

# Verbose
pytest -vv -s

# Show slowest
pytest --durations=10
```

---

## CI/CD

GitHub Actions workflow triggers on:
- Pushes to `main`, `develop`
- Pull requests to `main`, `develop`

Runs on Python 3.11 and 3.12.

---

## Troubleshooting

**ModuleNotFoundError: No module named 'pytest'**
```bash
pip install pytest pytest-asyncio
```

**ImportError: No module named 'shared'**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/shared"
# Or on Windows:
set PYTHONPATH=%PYTHONPATH%;%cd%\shared
```

**RabbitMQ/Redis errors in integration tests**
- Tests use mocks by default (no services needed)
- For real services: `docker-compose up -d`

---

## Common Commands

```bash
# Run all tests with coverage
pytest --cov=shared --cov=services -v

# Generate coverage report
pytest --cov=shared --cov=services --cov-report=html
open htmlcov/index.html  # View report

# Run tests excluding slow tests
pytest -m "not slow"

# Run tests verbosely
pytest -vv -s

# Run single test with detailed output
pytest -vv -s path/to/test.py::TestClass::test_name
```

---

## Test Categories

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.failure_mode` - Failure scenarios
- `@pytest.mark.intervals` - Interval tests
- `@pytest.mark.idempotency` - Idempotency tests
- `@pytest.mark.rabbit` - RabbitMQ tests
- `@pytest.mark.booking_lifecycle` - Booking tests
- `@pytest.mark.slow` - Slow running tests

---

## Fixtures Available

**Mocks:**
- `redis_mock` - Redis client
- `rabbit_channel_mock` - RabbitMQ channel
- `rabbit_message_mock` - Message

**Data:**
- `sample_booking_data` - Booking data
- `sample_event` - Domain event
- `sample_intervals` - Time intervals

---

Keep this handy for quick reference! 🚀
