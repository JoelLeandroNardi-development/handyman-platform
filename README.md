# Smart Handyman Marketplace — Microservices Backend

This repo is a microservices backend for a TaskRabbit/Uber-style “find a handyman + reserve a time slot + confirm/cancel” workflow.

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
- [Domain model](#domain-model)
- [Event bus contract](#event-bus-contract)
- [Core workflows](#core-workflows)
- [How to run](#how-to-run)
- [Configuration](#configuration)
- [Observability & debugging](#observability--debugging)
- [Failure scenarios to test](#failure-scenarios-to-test)
- [Pending architectural items](#pending-architectural-items)
- [Planned future functions](#planned-future-functions)
- [Testing plan (next)](#testing-plan-next)

---

## High-level architecture

```
   Client
     |
     v
  Gateway  --------------------->  Booking Service (DB: bookings + outbox)
     |                                   |
     | HTTP /match                        | publish booking.* via outbox
     v                                   v
  Match Service (Redis cache/projections) RabbitMQ exchange: domain_events
     |                                   ^
     | (Approach A removes HTTP calls)    |
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
- **consumer** (booking.* events → updates reservations/slots and emits slot.* events)

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
  "data": { }
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
  {"email":"handyman@test.com","slots":[{"start":"...","end":"..."}]}
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

## Testing plan (next)

1) Unit tests
- overlap logic
- reservation idempotency/TTL behavior
- match bucketing + distance + overlap (pure functions)

2) Integration tests (docker compose)
- Booking ↔ Availability lifecycle:
  - requested → reserved → confirmed
  - requested → rejected
  - reserved → expired
  - canceled → released

3) Failure-mode tests
- RabbitMQ down
- consumer restarts
- DLQ/retry behavior

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
