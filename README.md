# Smart Handyman Marketplace — Microservices Backend

This repository contains the backend for a handyman marketplace: users search for nearby handymen, inspect availability, create bookings, confirm or cancel them, and receive event-driven updates as the booking lifecycle progresses.

The frontend app lives here:

- [handyman-frontend](https://github.com/JoelLeandroNardi-development/handyman-frontend)

## What this project uses

- **FastAPI** for HTTP services
- **PostgreSQL** for relational service state
- **Redis** for availability state, reservations, projections, caches, and idempotency
- **RabbitMQ** for inter-service domain events
- **SQLAlchemy async** for database access
- **aio-pika** for RabbitMQ publishing and consumption
- **Docker Compose** for local orchestration
- **Pytest + GitHub Actions** for test automation

---

## Repository overview

```text
.
├── services/
│   ├── auth-service
│   ├── availability-service
│   ├── booking-service
│   ├── gateway-service
│   ├── handyman-service
│   ├── match-service
│   ├── notification-service
│   ├── search-service
│   └── user-service
├── shared/
│   ├── core/
│   ├── schemas/
│   ├── __init__.py
│   └── pyproject.toml
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── failure_mode/
│   └── service_loader.py
├── docker-compose.yml
├── pytest.ini
├── requirements-test.txt
└── .github/workflows/tests.yml
```

---

## Architecture at a glance

This backend uses a **service-per-domain** approach.

### Main ideas

- Each service owns its own write model and persistence.
- Cross-service communication happens primarily through **domain events** on RabbitMQ.
- Database-backed services publish through a **SQL outbox**.
- Redis-backed flows use Redis for fast state and transient booking/availability coordination.
- Read-heavy flows, especially matching, rely on **caches and projections** instead of synchronous fan-out wherever possible.
- Services follow a mostly consistent internal layout:
  - `api/`
  - `application/`
  - `domain/`
  - `infrastructure/`

### High-level flow

```text
Client
  |
  v
Gateway
  |
  +--> Auth
  +--> User
  +--> Handyman
  +--> Match
  +--> Availability
  +--> Booking
  +--> Notification

Booking <----events----> Availability
   |                         |
   +------events------------> Notification
   |
   +------events------------> Match projections
Handyman/User ----events----> Match projections
```

---

## Service summary

## gateway-service

The public entrypoint and façade for the rest of the system.

Responsibilities:

- route aggregation
- auth propagation
- RBAC-aware administrative endpoints
- breaker and health aggregation
- service-to-service façade for frontend clients

The gateway has a slightly different internal structure from the domain services and includes dedicated folders for:

- `breakers/`
- `clients/`
- `routes/`
- `utils/`

---

## auth-service

Authentication and token lifecycle service.

Responsibilities:

- registration/login flows
- token issuance and refresh
- password reset / verification flows
- auth-user management

This service is currently simpler and flatter internally than the other domain services.

---

## user-service

User profile service.

Responsibilities:

- user creation and updates
- location updates
- event emission for downstream consumers

Typical events:

- `user.created`
- `user.updated`
- `user.location_updated`
- `user.deleted`

---

## handyman-service

Handyman profile and skill service.

Responsibilities:

- handyman profiles
- location updates
- skills / catalog integration
- handyman-side profile data used downstream by matching

Typical events include handyman profile and location changes.

---

## availability-service

Availability and reservation coordination service.

Responsibilities:

- store handyman availability slots
- check interval overlap
- create temporary reservations
- confirm/release/expire reservations
- emit availability and slot lifecycle events

Key traits:

- Redis-backed
- worker-driven cleanup for expired reservations
- event-driven coordination with booking-service

This service includes a `workers/` folder because it runs background loops in addition to HTTP endpoints.

---

## booking-service

Booking lifecycle service.

Responsibilities:

- create booking requests
- manage booking status transitions
- emit booking commands/events
- react to slot lifecycle events from availability-service

Typical booking lifecycle states include:

- pending/requested
- reserved
- confirmed
- failed/rejected
- canceled
- expired
- completed

---

## match-service

Candidate selection and ranking service.

Responsibilities:

- find matching handymen for a skill, location, and time window
- use cached/projection-friendly read paths
- combine availability and handyman signals
- score and rank candidate results

This service is read-heavy by nature and is the best example of projection-oriented behavior in the repo.

---

## notification-service

Event-driven notification fanout service.

Responsibilities:

- consume booking/slot lifecycle events
- map domain events into notification intents
- persist and expose notifications
- manage read/unread state and notification preferences

The application layer was split so notification mapping is now more modular instead of being one oversized mapper module.

---

## search-service

A smaller service placeholder / future expansion point for search-specific concerns.

Right now the platform’s practical search/match behavior is centered more heavily in `match-service`.

---

## Shared package

The shared library has been refactored away from the old `shared/shared/...` layout into a cleaner package root:

```text
shared/
├── core/
└── schemas/
```

## `shared.core`

Cross-cutting infrastructure and utility code used by multiple services.

Current areas include:

- `auth/`
- `db/`
- `messaging/`
- `outbox/`
- `utils/`

Examples of what lives there:

- DB session/dependency helpers
- CRUD helpers
- RabbitMQ helpers
- consumer helpers
- outbox helpers and workers
- interval utilities
- role helpers

## `shared.schemas`

Shared request/response/domain schemas imported across services.

Current schema modules include:

- `auth.py`
- `availability.py`
- `bookings.py`
- `handymen.py`
- `match.py`
- `notifications.py`
- `users.py`

The goal of the shared package is simple:

- keep service code thin
- centralize generic infrastructure
- keep domain-specific business logic inside the owning service

---

## Internal service layout

Most services now follow this shape:

```text
app/
├── api/
├── application/
├── domain/
├── infrastructure/
├── __init__.py
└── main.py
```

### What goes where

- `api/`: FastAPI routers, dependencies, transport concerns
- `application/`: use cases, command/query services, mappers
- `domain/`: models, schemas, policies, domain concepts
- `infrastructure/`: DB, cache, MQ, repositories, external adapters

This keeps route handlers thin and pushes orchestration into application services.

---

## Event-driven design

RabbitMQ is used as the domain event bus.

### Event shape

Events follow a common envelope shape across services:

```json
{
  "event_id": "uuid",
  "event_type": "booking.requested",
  "occurred_at": "2026-03-04T10:17:56.504910+00:00",
  "source": "booking-service",
  "data": {}
}
```

### Eventing principles used in this repo

- services publish events after local state changes
- database-backed services use an **outbox pattern**
- consumers are designed to be **idempotent**
- services aim for **best-effort startup** when dependencies are temporarily unavailable
- read-side services can update projections or invalidate caches based on events

---

## Core business workflows

## 1. Availability update

A handyman sets or clears availability.

Flow:

1. availability-service stores slot state in Redis
2. availability-service emits an `availability.updated` event
3. downstream readers such as match-service can refresh projections or invalidate caches

---

## 2. Booking request

A user requests a booking.

Flow:

1. booking-service creates the booking locally
2. booking-service writes an outbox event such as `booking.requested`
3. availability-service consumes the event
4. availability-service either reserves the slot or rejects it
5. booking-service reacts to the resulting slot event and updates booking state

---

## 3. Booking confirmation

Once a reservation exists, the booking can be confirmed.

Flow:

1. booking-service emits a confirmation request event
2. availability-service finalizes the slot mutation
3. availability-service emits a confirmation event
4. booking-service marks the booking confirmed

---

## 4. Booking cancel / release

If a booking is canceled or released:

1. booking-service emits the appropriate cancel/request event
2. availability-service releases the reservation or slot hold
3. downstream services update state as needed
4. notification-service can fan out customer/handyman notifications

---

## 5. Reservation expiry

Availability-side temporary reservations can expire.

Flow:

1. worker detects expired reservations
2. reservation is removed
3. expiry/release event is emitted
4. booking-service reconciles booking state accordingly

---

## 6. Matching

The client queries for candidate handymen.

Flow:

1. match-service normalizes inputs
2. handymen are sourced from local data/projections/caches
3. availability and trust signals are combined
4. candidates are scored and ranked
5. the result is returned as a read-model-style response

---

## Running locally

## Prerequisites

- Docker
- Docker Compose v2+
- Python 3.14.3 for local non-Docker work

The repository is now standardized on Python 3.14.3 across local development,
Docker images, and GitHub Actions. The repository root includes a
`.python-version` file so pyenv, asdf, uv, and compatible tooling can pick up
the same interpreter automatically.

## Start everything

From the repository root:

```bash
docker compose up --build
```

## Stop everything

```bash
docker compose down
```

## Reset volumes

```bash
docker compose down -v
```

---

## Runtime services in Docker Compose

The Compose setup currently includes:

- `postgres`
- `notification-db`
- `redis`
- `rabbitmq`
- `auth-service`
- `user-service`
- `handyman-service`
- `availability-service`
- `match-service`
- `booking-service`
- `notification-service`
- `gateway-service`

Gateway is exposed on:

- `http://localhost:8000`

RabbitMQ management UI is exposed on:

- `http://localhost:15672`

---

## Configuration

Configuration is mostly environment-variable driven.

Common examples:

### Databases

- `AUTH_DB`
- `USER_DB`
- `HANDYMAN_DB`
- `BOOKING_DB`
- `MATCH_DB`
- `NOTIFICATION_DB`

### Messaging

- `RABBIT_URL`
- `EXCHANGE_NAME`
- `DOMAIN_EVENTS_EXCHANGE`
- `NOTIFICATION_QUEUE`

### Redis

- `REDIS_URL`

### Auth

- `JWT_SECRET`
- `JWT_ALGORITHM`

For local Docker runs, most of these are already wired through `docker-compose.yml`.

---

## Testing

The repository includes:

- `tests/unit`
- `tests/integration`
- `tests/failure_mode`

There is also a custom `tests/service_loader.py` to support service module loading in tests, which matters because services now use nested internal packages instead of older flat module layouts.

## Install test dependencies

```bash
python -m pip install -r requirements-test.txt
```

## Install the shared package in editable mode

```bash
cd shared
python -m pip install -e ".[test]"
cd ..
```

## Run all tests

```bash
pytest tests/ -v
```

## Run by group

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/failure_mode/ -v
```

## Useful markers

The repo currently registers markers such as:

- `unit`
- `integration`
- `failure_mode`
- `rabbit`
- `idempotency`
- `intervals`
- `booking_lifecycle`
- `slow`
- `asyncio`

---

## CI

GitHub Actions runs automated tests on:

- Python 3.14.3

The test workflow also provisions:

- PostgreSQL
- RabbitMQ
- Redis

The CI pipeline currently installs:

- test dependencies
- the shared package in editable mode
- each service’s runtime requirements

Then it runs:

- unit tests
- integration tests
- failure-mode tests
- coverage reporting

---

## Design goals

This codebase is optimized around a few practical backend goals:

- keep service ownership clear
- keep API routes thin
- centralize orchestration in application services
- use shared code for infrastructure, not for domain leakage
- use eventing for cross-service state transitions
- keep read paths cache/projection friendly
- favor straightforward patterns over framework-heavy abstractions

In practice, the current codebase leans toward:

- lightweight CQRS-style separation in services
- outbox-backed event publishing
- idempotent consumers
- shared schemas and shared infrastructure utilities
- Docker-first local development
- pragmatic, testable service boundaries

---

## Current status

This backend is no longer just a rough prototype. It now has:

- a consistent service layout across the main services
- a cleaned-up shared package structure
- event-driven booking/availability coordination
- test automation and CI coverage
- a gateway façade for client access
- modularized notification mapping and cleaner service boundaries

The project is still evolving, but the current codebase is already a solid backend foundation for the marketplace workflow.

---

## Suggested next areas of work

Some likely next steps for the platform:

- continue hardening projections and read models
- improve observability and metrics
- expand notification delivery options
- enrich booking/business-rule workflows
- push more match/search behavior into production-grade ranking and filtering
- grow the frontend against the now-cleaner backend contracts

---

## License

This repository is licensed under the GPL-3.0 license.
