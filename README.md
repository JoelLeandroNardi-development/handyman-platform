# Smart Handyman Marketplace — Microservices Backend

This repo is a microservices backend for a TaskRabbit/Uber-style “find a handyman + reserve a time slot + confirm/cancel” workflow.

For the frontend app of it, see: https://github.com/JoelLeandroNardi-development/handyman-frontend (this is even on an earlier stage than this one!)

It uses:

- **FastAPI** services (Python)
- **Postgres** (SQL state + SQL outbox pattern) via **SQLAlchemy async**
- **Redis** (availability state + reservations + Redis outbox; also match cache/projections)
- **RabbitMQ** (domain event bus) via **aio-pika**
- **Gateway service** (API façade, auth + RBAC, health checks, circuit breakers)

> Current milestone: **Backend eventing and reservation lifecycle works end-to-end** (Booking ↔ Availability via RabbitMQ), and we are documenting/cleaning before starting the frontend and adding tests.

---

## Table of contents

- [High-level architecture](#high-level-architecture)
- [Services](#services)
- [Shared library (`shared/shared/`)](#shared-library-sharedshared)
- [Domain model](#domain-model)
- [Event bus contract](#event-bus-contract)
- [Core workflows](#core-workflows)
- [How to run](#how-to-run)
- [Configuration](#configuration)
- [Observability & debugging](#observability--debugging)
- [Failure scenarios to test](#failure-scenarios-to-test)
- [Pending architectural items](#pending-architectural-items)
- [Planned future functions](#planned-future-functions)
- [Testing and CI status (March 2026)](#testing-and-ci-status-march-2026)

---

## High-level architecture

```
   Client
     |
     v
  Gateway  --------------------->  Booking Service (DB: bookings + outbox)
     |                                   |
     | HTTP /match                       | publish booking.* via outbox
     v                                   v
  Match Service (Redis cache/projections) RabbitMQ exchange: domain_events
     |                                   ^
     | (Approach A removes HTTP calls)   |
     v                                   |
Availability Service (Redis: slots + reservations + Redis outbox)
     |
     | publish slot.* + availability.updated via outbox
     v
RabbitMQ exchange: domain_events  ---> Booking Service consumes slot.*
```

**Key principles**

- **Outbox everywhere** (SQL outbox for DB-backed services; Redis outbox for Availability).
- **Best-effort startup**: services should not crash if RabbitMQ is temporarily down.
- **Mandatory publish**: publishers use `mandatory=True` to fail on unroutable messages (prevents outbox marking SENT incorrectly).
- **Idempotent consumers**: Redis idempotency markers (`processed_event:{event_id}`) to avoid double-processing.

---

## Services

### gateway-service

**Role:** API façade + RBAC + circuit breakers + system health.

Key endpoints:

- `GET /health`
- `GET /system/health` (admin)
- `GET /system/breakers` (admin)
- `POST /system/breakers/{name}/open|close` (admin)
- Proxies business endpoints: `/users`, `/handymen`, `/availability`, `/match`, `/bookings`, plus auth.

### auth-service

**Role:** authentication (JWT issuance). (Implementation not fully detailed here but wired in compose.)

### user-service

**State:** Postgres (`users` + `outbox_events`)  
**Publishes:** `user.created`, `user.location_updated` via SQL outbox

### handyman-service

**State:** Postgres (`handymen` + `outbox_events`)  
**Publishes:** `handyman.created`, `handyman.location_updated` via SQL outbox

### availability-service

**State:** Redis (availability slots + reservations + expiry index) + Redis outbox

**Consumes**

- `booking.requested`
- `booking.confirm_requested`
- `booking.cancel_requested`

**Publishes (via Redis outbox)**

- `slot.reserved`
- `slot.rejected`
- `slot.confirmed`
- `slot.released`
- `slot.expired`
- `availability.updated` **(Approach A: includes full slots payload)**

Background loops:

- **outbox worker** (publish from Redis outbox to RabbitMQ)
- **expiry worker** (reservation TTL cleanup → emits `slot.expired`)
- **consumer** (booking._ events → updates reservations/slots and emits slot._ events)

### booking-service

**State:** Postgres (`bookings` + `outbox_events`)

**Publishes (via SQL outbox)**

- `booking.requested`
- `booking.confirm_requested`
- `booking.cancel_requested`

**Consumes**

- `slot.reserved`
- `slot.rejected`
- `slot.confirmed`
- `slot.expired`
- `slot.released` (optional acknowledgement)

Background loop:

- **outbox worker** (drains SQL outbox → publishes domain events)

### match-service

**Role:** returns nearby candidate handymen for a skill/time window, with caching and (in the newer design) **local projections**.

Current direction:

- **Stop calling handyman-service at request time** by maintaining a handyman projection (Redis) fed by `handyman.created` + `handyman.location_updated`.
- **Approach A**: stop calling availability-service at request time by using availability projection fed by `availability.updated` which includes full slots.

---

## Shared library (`shared/shared/`)

All cross-cutting code lives in the `shared` Python package so each microservice stays thin. Services install it as a local dependency and import what they need.

### Module overview

```
shared/shared/
├── consumer.py        # RabbitMQ consumer with retry + DLQ
├── crud_helpers.py    # fetch_or_404, apply_partial_update
├── db.py              # SQLAlchemy async engine/session factory
├── events.py          # Domain event envelope builder
├── idempotency.py     # Redis-based idempotency (SET NX)
├── intervals.py       # Datetime interval math (overlaps, fully_contains)
├── mq.py              # RabbitMQ publisher + config
├── outbox_helpers.py  # Insert outbox row helper
├── outbox_model.py    # OutboxEvent model factory
├── outbox_worker.py   # Background outbox drain loop
├── roles.py           # Role validation + normalization
└── schemas/           # Pydantic schemas shared across services
    ├── auth.py
    ├── availability.py
    ├── bookings.py
    ├── handymen.py
    ├── match.py
    └── users.py
```

### `db.py` — Database factory

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `create_db` | `(env_var, *, echo=True) -> (engine, SessionLocal, Base)` | Reads a Postgres URL from the named env var and returns an async engine, session maker, and declarative Base. |
| `make_get_db` | `(SessionLocal) -> async generator` | Returns a FastAPI-compatible `get_db` dependency that yields an `AsyncSession`. |

**Usage (per service):**
```python
from shared.shared.db import create_db
engine, SessionLocal, Base = create_db(“BOOKING_DB”)
```

### `events.py` — Event envelope builder

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `utc_now_iso` | `() -> str` | Current UTC time as ISO-8601 string. |
| `build_event` | `(event_type, data, *, source, event_id=None, occurred_at=None) -> dict` | Builds a standard event envelope with `event_id`, `event_type`, `occurred_at`, `source`, `data`. |
| `build_event_jsonable` | `(event_type, data, *, source, ...) -> dict` | Same as `build_event` but runs the result through FastAPI's `jsonable_encoder`. |
| `make_event_builder` | `(service_name) -> Callable` | Factory returning a `build_event(event_type, data)` closure pre-bound to the given service name. |

**Usage:**
```python
from shared.shared.events import make_event_builder
build_event = make_event_builder(“booking-service”)
evt = build_event(“booking.requested”, {“booking_id”: 42})
```

### `mq.py` — RabbitMQ publisher

| Symbol | Kind | Description |
|--------|------|-------------|
| `RabbitConfig` | Frozen dataclass | Holds `url` and `exchange_name`. `RabbitConfig.from_env(required=False)` reads from `RABBIT_URL` / `EXCHANGE_NAME` env vars. |
| `RabbitPublisher` | Class | Manages a persistent connection, channel, and TOPIC exchange. Methods: `start()`, `close()`, `publish(*, routing_key, payload, ...)`. Auto-reconnects. No-op when disabled. |
| `rabbit_connect` | `async (cfg) -> RobustConnection \| None` | Opens a robust RabbitMQ connection from config. |
| `create_publisher` | `(*, required=True) -> (publisher, config)` | Convenience factory: creates config from env + publisher in one call. |

### `consumer.py` — RabbitMQ consumer with retry + DLQ

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `setup_consumer_topology` | `(*, channel, exchange_name, queue_name, retry_queue, dlq_queue, routing_keys, retry_delay_ms, prefetch=50) -> (exchange, queue)` | Declares a TOPIC exchange, main queue, retry queue (with TTL dead-lettering back to main), and DLQ. Binds main queue to the given routing keys. |
| `run_consumer_with_retry_dlq` | `(*, channel, exchange_name, queue_name, retry_queue, dlq_queue, routing_keys, handler, retry_delay_ms=5000, max_retries=3, ...) -> None` | Starts consuming. On failure retries via the retry queue (with `x-retry-count` header). After `max_retries`, rejects to DLQ. |

### `outbox_model.py` — OutboxEvent model factory

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `make_outbox_event_model` | `(Base) -> OutboxEvent` | Given a SQLAlchemy declarative `Base`, returns an `OutboxEvent` ORM class mapped to `outbox_events`. Columns: `id`, `event_id`, `event_type`, `routing_key`, `payload` (JSON), `status`, `attempts`, `last_error`, `created_at`, `published_at`. |

### `outbox_worker.py` — Background outbox drain loop

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `run_outbox_loop` | `(*, stop_event, SessionLocal, OutboxEvent, publisher, service_label, max_attempts=20, poll_interval=1.0, batch_size=50) -> None` | Claims `PENDING` rows with `SELECT ... FOR UPDATE SKIP LOCKED`, publishes each via the publisher, marks `SENT` on success or increments attempts on failure. |
| `make_outbox_stats` | `(SessionLocal, OutboxEvent) -> dict` | Returns outbox row counts grouped by status (e.g. `{“type”: “sql”, “pending”: 3, “sent”: 120}`). |

### `outbox_helpers.py` — Insert outbox row

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `add_outbox_event` | `(db, OutboxEvent, event: dict) -> None` | Adds a `PENDING` outbox row to the session. Extracts `event_id`, `event_type` from the event dict. |

**Usage:**
```python
from shared.shared.outbox_helpers import add_outbox_event
evt = build_event(“booking.requested”, data)
add_outbox_event(db, OutboxEvent, evt)
await db.commit()
```

### `crud_helpers.py` — Generic CRUD utilities

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `fetch_or_404` | `async (db, model, *, filter_column, filter_value, detail=”Not found”)` | SELECT for a single row; raises `HTTPException(404)` if missing. |
| `apply_partial_update` | `(entity, data, fields: list[str]) -> None` | Copies non-`None` fields from a Pydantic model onto an ORM entity. |

**Usage:**
```python
from shared.shared.crud_helpers import fetch_or_404, apply_partial_update

booking = await fetch_or_404(
    db, Booking,
    filter_column=Booking.booking_id, filter_value=bid,
    detail=”Booking not found”,
)
apply_partial_update(user, update_data, [“first_name”, “last_name”, “phone”])
```

### `idempotency.py` — Redis-based idempotency

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `IDEMPOTENCY_DEFAULT_TTL_SECONDS` | `3600` | Default TTL (1 hour). |
| `already_processed` | `async (*, redis_client, event_id, ttl_seconds=3600, prefix=”processed_event”) -> bool` | Atomic `SET NX` on `{prefix}:{event_id}`. Returns `True` if the event was already processed. |

### `roles.py` — Role validation

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `ALLOWED_ROLES` | `frozenset({“user”, “handyman”, “admin”})` | Valid role strings. |
| `normalize_roles` | `(roles, *, allow_empty=False, default=None) -> list[str]` | Lowercases, trims, deduplicates, validates against `ALLOWED_ROLES`. Raises `ValueError` on invalid roles. |

### `intervals.py` — Datetime interval math

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `overlaps` | `(a_start, a_end, b_start, b_end) -> bool` | Returns `True` if two time intervals overlap. |
| `fully_contains` | `(outer_start, outer_end, inner_start, inner_end) -> bool` | Returns `True` if the outer interval fully contains the inner. |

### `schemas/` — Shared Pydantic schemas

All domain schemas live here so downstream services and the gateway import from one source of truth.

| Module | Key Classes |
|--------|-------------|
| `auth.py` | `Register`, `Login`, `TokenResponse`, `AuthUserResponse`, `UpdateAuthUserPassword`, `UpdateAuthUserRoles`, `UpdateAuthUser` |
| `availability.py` | `AvailabilitySlot`, `SetAvailability`, `OverlapRequest` |
| `bookings.py` | `CreateBooking`, `BookingResponse`, `CancelBooking`, `ConfirmBookingResponse`, `CancelBookingResponse`, `CompleteBookingResponse`, `RejectBookingRequest`, `RejectBookingResponse`, `UpdateBookingAdmin` |
| `handymen.py` | `CreateHandyman`, `UpdateLocation`, `UpdateHandyman`, `HandymanResponse`, skill catalog schemas (`SkillCatalogReplaceRequest`, `SkillCatalogPatchRequest`, `SkillCatalogFlatResponse`), review schemas (`CreateHandymanReview`, `HandymanReviewResponse`) |
| `match.py` | `MatchRequest`, `MatchResult`, `MatchLogResponse`, `UpdateMatchLog` |
| `users.py` | `CreateUser`, `UpdateUserLocation`, `UpdateUser`, `UserResponse` |

Each downstream service re-exports from shared in its local `schemas.py` for backward compatibility:
```python
# services/booking-service/app/schemas.py
from shared.shared.schemas.bookings import *
```

---

## Domain model

### Availability “slots” (Availability service)

Raw calendar windows a handyman is available.

Example:

- 10:00–14:00
- 15:00–18:00

Stored per handyman key:

- `availability:{email}` → Redis list entries like `start|end`.

### Reservation (Availability service)

Temporary hold for a specific booking request; prevents double booking between requested and confirmed.

- TTL (e.g., 5 minutes)
- Stored as:
  - `reservation:{booking_id}` (payload includes handyman_email and window)
  - `reservations_by_handyman:{email}` set
  - `reservation_expiry` zset for expiry scanning

### Booking (Booking service)

Represents the user’s booking request lifecycle.

Statuses:

- `PENDING` → initial
- `RESERVED` → availability reserved
- `CONFIRMED` → confirmed
- `FAILED` → slot rejected
- `EXPIRED` → reservation expired before confirmation
- `CANCELED` → canceled

---

## Event bus contract

RabbitMQ:

- Exchange: **topic** exchange, durable
- Name: `domain_events` (default)
- Routing key == `event_type` (strict contract)

### Standard event envelope (shared)

All services should build events using `shared/shared/events.py`:

```json
{
  "event_id": "uuid",
  "event_type": "booking.requested",
  "occurred_at": "2026-03-04T10:17:56.504910+00:00",
  "source": "booking-service",
  "data": {}
}
```

- `event_id`: globally unique id, used for downstream idempotency
- `event_type`: also used as routing key
- `occurred_at`: ISO-8601 UTC string
- `source`: producing service name
- `data`: payload

### Important publishing behavior

- `mandatory=True` publishing is enabled in shared publisher.
- If no queue is bound to the routing key, publish fails and the outbox retries (prevents false “SENT”).

---

## Core workflows

### Flow A — Handyman updates availability slots (Approach A)

A1. Set/clear slots (HTTP)

- `POST /availability/{email}` with slots
- `DELETE /availability/{email}` clears

A2. Emit domain event (via Redis outbox)

- `availability.updated` (routing key: `availability.updated`)
- **data includes full slots**:
  ```json
  { "email": "handyman@test.com", "slots": [{ "start": "...", "end": "..." }] }
  ```

A3. Match reacts

- Match consumes `availability.updated` and invalidates cached match buckets (and/or stores availability projection for “no HTTP calls” mode).

---

### Flow B — User searches for a handyman (Match)

User → Gateway → Match service `POST /match`

Planned (Approach A projection path):

1. Normalize skill
2. Read candidate handymen from local projection
3. Filter by distance
4. Check desired window overlaps projected availability slots (no HTTP call)
5. Return sorted results + cache

Degraded behavior:

- If projections are missing (bootstrap or events disabled), return candidates with `availability_unknown=true` and short TTL cache.

---

### Flow C — Booking + reservation lifecycle (critical path)

C1. Booking created

- Client → Gateway → Booking `POST /bookings`
- Booking writes:
  - booking row (`PENDING`)
  - outbox row `booking.requested`
- Booking outbox publishes `booking.requested`

C2. Availability reserves or rejects
Availability consumes `booking.requested`:

1. Check handyman has overlapping slot
2. Create reservation (TTL) if no reservation conflict
3. Emit:
   - `slot.reserved` or `slot.rejected`

C3. Booking updates status
Booking consumes slot events:

- `slot.reserved` → booking `RESERVED`
- `slot.rejected` → booking `FAILED` + reason

---

### Flow D — Confirm booking

D1. Confirm requested

- Client → Gateway → Booking `POST /bookings/{id}/confirm`
- Booking emits `booking.confirm_requested` via outbox

D2. Availability finalizes slot
Availability consumes `booking.confirm_requested`:

1. Verify reservation exists
2. Remove/split overlapping slot(s) from availability slots list
3. Delete reservation
4. Emit `slot.confirmed`

D3. Booking marks confirmed
Booking consumes `slot.confirmed` → `CONFIRMED`

---

### Flow E — Cancel booking

E1. Cancel requested

- Client → Gateway → Booking `POST /bookings/{id}/cancel`
- Booking sets status `CANCELED`
- Emits `booking.cancel_requested` via outbox

E2. Availability releases reservation
Consumes cancel request:

1. Delete reservation if exists (idempotent)
2. Emit `slot.released`

---

### Flow F — Reservation expiry (auto cleanup)

Availability expiry worker:

1. Detect expired reservations in zset
2. Delete reservation
3. Emit `slot.expired`

Booking consumes `slot.expired`:

- If booking still `PENDING` or `RESERVED` → mark `EXPIRED`

---

## How to run

### Prerequisites

- Docker + Docker Compose v2+
- (Optional for local non-docker runs) Python 3.11

### Start everything

From repo root:

```bash
docker compose up --build
```

Services:

- Gateway: `http://localhost:8000`
- RabbitMQ UI: `http://localhost:15672` (guest/guest)
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

### Stop

```bash
docker compose down
```

Reset state (drops volumes):

```bash
docker compose down -v
```

---

## Configuration

### RabbitMQ

In compose, each service that uses RabbitMQ is passed:

- `RABBIT_URL=amqp://guest:guest@rabbitmq:5672/`
- `EXCHANGE_NAME=domain_events`

**Recommendation:** also add these to `.env` for local `uvicorn` runs outside Docker.

### Postgres connection env vars

Each DB-backed service sets its own `*_DB` env var, e.g.:

- `BOOKING_DB=postgresql+asyncpg://admin:admin@postgres:5432/booking_db`

### Redis URL

- `REDIS_URL=redis://redis:6379/0`

---

## Observability & debugging

### Health endpoints

Each service exposes a basic `/health`.

Gateway (admin):

- `GET /system/health` → checks each service `/health` and reports latency.

Recommended additions (some already implemented in match-service):

- include `events_enabled`, `exchange_name`, `rabbit_url_set`
- Outbox stats:
  - SQL outbox: counts of `PENDING`, `FAILED`
  - Redis outbox: lengths of pending/processing/dlq lists

### Debug Rabbit endpoints (optional)

Per consumer service:

- `GET /debug/rabbit` returning queue name, exchange, routing keys bound.

Match-service already includes:

- `/debug/rabbit` (queue/routing keys + exchange)

### RabbitMQ UI checks

Use RabbitMQ management to confirm:

- Exchange `domain_events` exists
- Queues exist and bindings are correct:
  - `availability_service_booking_events` bound to `booking.*`
  - `booking_service_domain_events` bound to `slot.*`
  - `match_service_domain_events` bound to `availability.updated`, `handyman.*`

---

## Failure scenarios to test

1. **Rabbit down on startup**
   - Start stack with Rabbit stopped or slow.
   - Services should still come up; publishers are “enabled but not ready”.
   - Outboxes retry until Rabbit returns.

2. **Kill availability-service**
   - Create a booking (Booking publishes `booking.requested`).
   - Restart availability.
   - Availability should consume and emit slot results; booking should converge.

3. **Unroutable message**
   - Temporarily remove consumer binding for a routing key.
   - Publish event with that routing key.
   - Outbox should **NOT mark SENT** (mandatory publish fails) and should keep retrying.

4. **Poison messages**
   - Force handler exceptions.
   - Consumer should retry up to max retries then send to DLQ.

---

## Planned future functions

### Search / geo improvements

Originally search was meant to find nearby handymen by geo radius.

Options:

1. **Redis GEO index** in Match (fast):
   - `GEOADD`, `GEORADIUS`
   - Combine with skill sets
2. **Materialized geo index** in Match:
   - Maintain buckets / precomputed grids (already present as cache buckets)
3. **Dedicated search-service revival**
   - If you need advanced ranking, full-text, or multi-criteria search:
     - geo + skill + ratings + availability signals
     - ranking/scoring model

### Booking enhancements

- richer cancellation rules (fees/deadlines)
- handyman-initiated confirm/cancel flows
- multi-slot booking or rescheduling

### Availability enhancements

- timezone normalization + validation
- “busy blocks” and calendar integrations
- reservation renewal/extension policies

### Operational maturity

- structured logging
- metrics (Prometheus) + tracing (OpenTelemetry)
- dashboards/alerts

---

## Testing and CI status (March 2026)

This section replaces the previous testing plan and serves as the consolidated testing reference for this repository.

### Current baseline

- 217 passing tests
- 96% combined coverage over `shared` and `services`
- Test tracks: unit, integration, and failure-mode

### Test structure

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
   integration/
      test_booking_lifecycle.py
   failure_mode/
      test_consumer_failures.py
```

Key test/config support files:

- `pytest.ini`
- `conftest.py`
- `requirements-test.txt`
- `Makefile`
- `run_tests.py`
- `.github/workflows/tests.yml`

### What is covered

Unit coverage includes:

- interval overlap and containment logic
- Redis idempotency behavior
- RabbitMQ consumer topology/retry/DLQ behavior
- shared event, role, DB, and CRUD helper behavior
- outbox worker claim/send/failure/retry loops
- match helper and projection/caching behavior
- availability reservation helpers
- gateway RBAC and circuit-breaker behavior
- shared schema validation across auth/users/handymen/bookings/availability/match

Integration coverage includes:

- booking lifecycle transitions with event-driven progression

Failure-mode coverage includes:

- retry and DLQ handling
- malformed payload handling
- consumer error path behavior

### Quick start

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

Optional editable shared install:

```bash
cd shared
pip install -e ".[test]"
cd ..
```

Run tests:

```bash
pytest tests/ -v
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/failure_mode/ -v
```

Run by marker:

```bash
pytest -m unit
pytest -m integration
pytest -m failure_mode
pytest -m intervals
pytest -m idempotency
pytest -m rabbit
pytest -m booking_lifecycle
```

Coverage commands:

```bash
pytest tests --cov=shared --cov=services --cov-report=term-missing --cov-report=xml
python -m coverage report
python -m coverage html
```

### CI workflow summary

Workflow file: `.github/workflows/tests.yml`

- Triggers: push/pull_request for `main` and `develop`
- Matrix: Python `3.11` and `3.12`
- Service containers: Postgres, RabbitMQ, Redis
- Stages: dependency install, unit tests, integration tests, failure-mode tests, Codecov upload, HTML coverage artifact

### Recent fixes applied

1. GitHub Actions/runtime updates

- `actions/checkout@v5`
- `actions/setup-python@v5`
- `actions/upload-artifact@v4`
- `codecov/codecov-action@v5`
- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`

2. Dependency conflict fixes

- removed invalid `unittest-mock==1.5`
- centralized test dependencies in `requirements-test.txt`
- kept service `requirements.txt` files runtime-only to avoid duplicate/conflicting test pins

3. Import and coverage execution fixes

- CI `PYTHONPATH` set to repo root to resolve `shared.shared.*` imports
- coverage invoked with `python -m coverage` to avoid shell path issues

### Troubleshooting

Missing pytest:

```bash
pip install pytest pytest-asyncio
```

`ModuleNotFoundError: No module named shared.shared`:

- Ensure `PYTHONPATH` points to repository root
- Do not set only the `shared` subdirectory as top-level path

Linux/macOS:

```bash
export PYTHONPATH="$(pwd)"
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = (Get-Location).Path
```

Dependency resolver conflicts:

- keep test-only dependencies in `requirements-test.txt`
- keep service requirement files runtime-only

### Remaining optional improvements

- close remaining uncovered branches in `shared/shared/events.py`, `shared/shared/mq.py`, `shared/shared/outbox_worker.py`, and `services/match-service/app/services.py`

---

## Appendix: docker-compose summary

RabbitMQ:

- `rabbitmq:3-management`
- ports: `5672`, `15672`

Postgres:

- `postgis/postgis:15-3.3`
- port `5432`

Redis:

- `redis:7`
- port `6379`

Gateway exposed:

- `8000:8000`

---

## Notes

- The system is designed so **writes** are local/transactional and **reads** can be cached/projection-driven.
- Outbox + mandatory publish + idempotency are the reliability backbone.
- Next major milestone: **projection-driven Match** + **frontend** + **tests**.
