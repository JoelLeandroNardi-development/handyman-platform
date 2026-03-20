from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import declarative_base

from shared.shared.outbox_model import make_outbox_event_model
from shared.shared.outbox_worker import (
    _claim_batch,
    _mark_failure,
    _mark_sent,
    make_outbox_stats,
    run_outbox_loop,
)


Base = declarative_base()
OutboxEventModel = make_outbox_event_model(Base)


class _BeginCtx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _SessionCtx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.unit
class TestOutboxWorkerHelpers:

    @pytest.mark.asyncio
    async def test_claim_batch_returns_scalar_rows(self):
        rows = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        db = MagicMock()
        db.execute = AsyncMock(return_value=result)

        claimed = await _claim_batch(db, OutboxEventModel, batch_size=2)

        assert claimed == rows

    @pytest.mark.asyncio
    async def test_mark_sent_executes_update(self):
        db = MagicMock()
        db.execute = AsyncMock()

        await _mark_sent(db, OutboxEventModel, 3)

        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_failure_marks_pending_below_max_attempts(self):
        db = MagicMock()
        db.execute = AsyncMock()

        await _mark_failure(db, OutboxEventModel, 3, 2, "boom", 5)

        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_make_outbox_stats_aggregates_counts(self):
        result = MagicMock()
        result.all.return_value = [("PENDING", 2), ("FAILED", 1), ("SENT", 7)]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        async def session_local():
            return None

        stats = await make_outbox_stats(lambda: _SessionCtx(session), OutboxEventModel)

        assert stats == {"type": "sql", "pending": 2, "failed": 1, "sent": 7}


@pytest.mark.unit
class TestRunOutboxLoop:

    @pytest.mark.asyncio
    async def test_run_outbox_loop_publishes_and_marks_sent(self, monkeypatch):
        stop_event = asyncio.Event()
        publisher = MagicMock()
        publisher.start = AsyncMock()
        publisher.publish = AsyncMock(side_effect=lambda **kwargs: stop_event.set())
        session = MagicMock()
        session.begin.return_value = _BeginCtx()
        ev = SimpleNamespace(id=1, routing_key="booking.requested", payload={"id": 1}, event_id="evt-1", attempts=0)

        monkeypatch.setattr("shared.shared.outbox_worker._claim_batch", AsyncMock(return_value=[ev]))
        monkeypatch.setattr("shared.shared.outbox_worker._mark_sent", AsyncMock())
        monkeypatch.setattr("shared.shared.outbox_worker._mark_failure", AsyncMock())

        await run_outbox_loop(
            stop_event=stop_event,
            SessionLocal=lambda: _SessionCtx(session),
            OutboxEvent=OutboxEventModel,
            publisher=publisher,
            poll_interval=0.01,
        )

        publisher.start.assert_awaited_once()
        publisher.publish.assert_awaited_once_with(
            routing_key="booking.requested",
            payload={"id": 1},
            message_id="evt-1",
        )

    @pytest.mark.asyncio
    async def test_run_outbox_loop_marks_failure_when_publish_raises(self, monkeypatch):
        stop_event = asyncio.Event()
        publisher = MagicMock()
        publisher.start = AsyncMock()

        async def fail_publish(**kwargs):
            stop_event.set()
            raise RuntimeError("publish failed")

        publisher.publish = AsyncMock(side_effect=fail_publish)
        session = MagicMock()
        session.begin.return_value = _BeginCtx()
        ev = SimpleNamespace(id=2, routing_key="booking.requested", payload={"id": 2}, event_id="evt-2", attempts=1)
        mark_failure = AsyncMock()

        monkeypatch.setattr("shared.shared.outbox_worker._claim_batch", AsyncMock(return_value=[ev]))
        monkeypatch.setattr("shared.shared.outbox_worker._mark_sent", AsyncMock())
        monkeypatch.setattr("shared.shared.outbox_worker._mark_failure", mark_failure)

        await run_outbox_loop(
            stop_event=stop_event,
            SessionLocal=lambda: _SessionCtx(session),
            OutboxEvent=OutboxEventModel,
            publisher=publisher,
            max_attempts=5,
            poll_interval=0.01,
        )

        mark_failure.assert_awaited_once_with(session, OutboxEventModel, 2, 2, "publish failed", 5)

    @pytest.mark.asyncio
    async def test_run_outbox_loop_retries_after_outer_error(self, monkeypatch):
        stop_event = asyncio.Event()
        publisher = MagicMock()
        publisher.start = AsyncMock()
        wait_calls = []

        async def fake_wait_for(awaitable, timeout):
            wait_calls.append(timeout)
            stop_event.set()
            await awaitable
            raise asyncio.TimeoutError()

        monkeypatch.setattr("shared.shared.outbox_worker.asyncio.wait_for", fake_wait_for)

        class FailingSessionFactory:
            def __call__(self):
                raise RuntimeError("db unavailable")

        await run_outbox_loop(
            stop_event=stop_event,
            SessionLocal=FailingSessionFactory(),
            OutboxEvent=OutboxEventModel,
            publisher=publisher,
            poll_interval=0.01,
        )

        assert 2.0 in wait_calls


@pytest.mark.unit
class TestBookingRejectedOutboxBehavior:
    """Verify outbox worker handles booking.rejected events correctly,
    covering the retry and idempotency acceptance criteria."""

    @pytest.mark.asyncio
    async def test_booking_rejected_event_published_and_marked_sent(self, monkeypatch):
        stop_event = asyncio.Event()
        publisher = MagicMock()
        publisher.start = AsyncMock()
        publisher.publish = AsyncMock(side_effect=lambda **kwargs: stop_event.set())
        session = MagicMock()
        session.begin.return_value = _BeginCtx()

        ev = SimpleNamespace(
            id=10,
            routing_key="booking.rejected",
            payload={"event_type": "booking.rejected", "data": {"booking_id": "b-001", "reason": "Unavailable"}},
            event_id="evt-rejected-1",
            attempts=0,
        )
        mark_sent = AsyncMock()

        monkeypatch.setattr("shared.shared.outbox_worker._claim_batch", AsyncMock(return_value=[ev]))
        monkeypatch.setattr("shared.shared.outbox_worker._mark_sent", mark_sent)
        monkeypatch.setattr("shared.shared.outbox_worker._mark_failure", AsyncMock())

        await run_outbox_loop(
            stop_event=stop_event,
            SessionLocal=lambda: _SessionCtx(session),
            OutboxEvent=OutboxEventModel,
            publisher=publisher,
            poll_interval=0.01,
        )

        publisher.publish.assert_awaited_once_with(
            routing_key="booking.rejected",
            payload=ev.payload,
            message_id="evt-rejected-1",
        )
        mark_sent.assert_awaited_once_with(session, OutboxEventModel, 10)

    @pytest.mark.asyncio
    async def test_booking_rejected_event_retried_on_publish_failure(self, monkeypatch):
        stop_event = asyncio.Event()
        publisher = MagicMock()
        publisher.start = AsyncMock()

        async def fail_publish(**kwargs):
            stop_event.set()
            raise RuntimeError("broker unreachable")

        publisher.publish = AsyncMock(side_effect=fail_publish)
        session = MagicMock()
        session.begin.return_value = _BeginCtx()

        ev = SimpleNamespace(
            id=11,
            routing_key="booking.rejected",
            payload={"event_type": "booking.rejected", "data": {"booking_id": "b-002"}},
            event_id="evt-rejected-2",
            attempts=3,
        )
        mark_failure = AsyncMock()

        monkeypatch.setattr("shared.shared.outbox_worker._claim_batch", AsyncMock(return_value=[ev]))
        monkeypatch.setattr("shared.shared.outbox_worker._mark_sent", AsyncMock())
        monkeypatch.setattr("shared.shared.outbox_worker._mark_failure", mark_failure)

        await run_outbox_loop(
            stop_event=stop_event,
            SessionLocal=lambda: _SessionCtx(session),
            OutboxEvent=OutboxEventModel,
            publisher=publisher,
            max_attempts=10,
            poll_interval=0.01,
        )

        mark_failure.assert_awaited_once_with(session, OutboxEventModel, 11, 4, "broker unreachable", 10)

    @pytest.mark.asyncio
    async def test_booking_rejected_event_marked_failed_after_max_attempts(self, monkeypatch):
        stop_event = asyncio.Event()
        publisher = MagicMock()
        publisher.start = AsyncMock()

        async def fail_publish(**kwargs):
            stop_event.set()
            raise RuntimeError("permanent failure")

        publisher.publish = AsyncMock(side_effect=fail_publish)
        session = MagicMock()
        session.begin.return_value = _BeginCtx()

        ev = SimpleNamespace(
            id=12,
            routing_key="booking.rejected",
            payload={"event_type": "booking.rejected", "data": {"booking_id": "b-003"}},
            event_id="evt-rejected-3",
            attempts=19,
        )
        mark_failure = AsyncMock()

        monkeypatch.setattr("shared.shared.outbox_worker._claim_batch", AsyncMock(return_value=[ev]))
        monkeypatch.setattr("shared.shared.outbox_worker._mark_sent", AsyncMock())
        monkeypatch.setattr("shared.shared.outbox_worker._mark_failure", mark_failure)

        await run_outbox_loop(
            stop_event=stop_event,
            SessionLocal=lambda: _SessionCtx(session),
            OutboxEvent=OutboxEventModel,
            publisher=publisher,
            max_attempts=20,
            poll_interval=0.01,
        )

        # attempts reaches max_attempts → _mark_failure transitions status to FAILED
        mark_failure.assert_awaited_once_with(session, OutboxEventModel, 12, 20, "permanent failure", 20)

    @pytest.mark.asyncio
    async def test_booking_completed_event_published_and_marked_sent(self, monkeypatch):
        stop_event = asyncio.Event()
        publisher = MagicMock()
        publisher.start = AsyncMock()
        publisher.publish = AsyncMock(side_effect=lambda **kwargs: stop_event.set())
        session = MagicMock()
        session.begin.return_value = _BeginCtx()

        ev = SimpleNamespace(
            id=20,
            routing_key="booking.completed",
            payload={"event_type": "booking.completed", "data": {"booking_id": "b-complete-001"}},
            event_id="evt-completed-1",
            attempts=0,
        )
        mark_sent = AsyncMock()

        monkeypatch.setattr("shared.shared.outbox_worker._claim_batch", AsyncMock(return_value=[ev]))
        monkeypatch.setattr("shared.shared.outbox_worker._mark_sent", mark_sent)
        monkeypatch.setattr("shared.shared.outbox_worker._mark_failure", AsyncMock())

        await run_outbox_loop(
            stop_event=stop_event,
            SessionLocal=lambda: _SessionCtx(session),
            OutboxEvent=OutboxEventModel,
            publisher=publisher,
            poll_interval=0.01,
        )

        publisher.publish.assert_awaited_once_with(
            routing_key="booking.completed",
            payload=ev.payload,
            message_id="evt-completed-1",
        )
        mark_sent.assert_awaited_once_with(session, OutboxEventModel, 20)