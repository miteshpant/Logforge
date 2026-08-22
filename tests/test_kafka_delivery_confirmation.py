"""
Tests for ENH-006 -- Kafka delivery must be confirmed, never assumed.

`aiokafka`'s `producer.send()` resolves once a record is buffered locally; the
future it RETURNS is what resolves on broker acknowledgement. The publisher
previously assigned that future and never awaited it, then recorded success
unconditionally -- so logs were silently dropped whenever the broker rejected or
throttled a write, while metrics reported 100% success.

Silent loss is the worst failure mode for an observability vendor: customers
discover it only when they need the data during an incident.

These tests use a fake producer to observe the acknowledgement contract. No
broker is required.
"""

import asyncio

import pytest

from events.publisher_manager import KafkaEventPublisher, PublisherConfig


class _RecordMetadata:
    def __init__(self, offset=42):
        self.offset = offset
        self.partition = 0
        self.topic = "test-topic"


class _FakeProducer:
    """
    Fake aiokafka producer.

    `send()` returns a future that resolves only when the broker "acknowledges",
    mirroring the real two-stage contract.
    """

    def __init__(self, *, ack=True, error=None, ack_delay=0):
        self.ack = ack
        self.error = error
        self.ack_delay = ack_delay
        self.sent = []
        self.acknowledged = []

    async def send(self, topic, value, partition=None, key=None):
        self.sent.append({"topic": topic, "value": value, "partition": partition})

        async def _delivery():
            if self.ack_delay:
                await asyncio.sleep(self.ack_delay)
            if self.error is not None:
                raise self.error
            self.acknowledged.append(topic)
            return _RecordMetadata()

        return asyncio.ensure_future(_delivery())


def _publisher(producer, max_batch_size=1):
    config = PublisherConfig(
        name="test", enabled=True, topics=[], max_batch_size=max_batch_size
    )
    pub = KafkaEventPublisher.__new__(KafkaEventPublisher)
    pub.config = config
    pub.producer = producer
    pub.admin_client = None
    pub.is_started = True
    from events.base import EventMetrics

    pub.metrics = EventMetrics()
    pub._pending_events = {}
    pub._batch_timer = None
    return pub


class _Event:
    def __init__(self, event_id="evt-1"):
        from types import SimpleNamespace

        self.event_type = "logs.batch.ingested"
        self.customer_id = "tenant-a"
        self.metadata = SimpleNamespace(event_id=event_id)

    def to_dict(self):
        return {"event_type": self.event_type, "customer_id": self.customer_id}

    def get_partition_key(self):
        return self.customer_id


# ---------------------------------------------------------------------------
# The core contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_future_is_awaited():
    """Success must mean the broker acknowledged, not merely that we enqueued."""
    producer = _FakeProducer(ack=True)
    pub = _publisher(producer)

    result = await pub._publish_single(_Event(), "test-topic")

    assert result is True
    assert producer.sent, "Event should have been enqueued"
    assert producer.acknowledged == ["test-topic"], (
        "The delivery future was never awaited -- this is the ENH-006 bug: "
        "the publisher reported success without broker acknowledgement."
    )


@pytest.mark.asyncio
async def test_broker_rejection_propagates():
    """A broker failure must surface, not be reported as success."""
    producer = _FakeProducer(error=RuntimeError("NotLeaderForPartition"))
    pub = _publisher(producer)

    with pytest.raises(RuntimeError, match="NotLeaderForPartition"):
        await pub._publish_single(_Event(), "test-topic")


@pytest.mark.asyncio
async def test_failed_delivery_is_not_counted_as_published():
    """Metrics must not claim success for events the broker never accepted."""
    producer = _FakeProducer(error=RuntimeError("broker down"))
    pub = _publisher(producer)

    with pytest.raises(RuntimeError):
        await pub._publish_single(_Event(), "test-topic")

    assert pub.metrics.events_published == 0, (
        "A rejected event must never increment the published counter."
    )


@pytest.mark.asyncio
async def test_successful_delivery_is_counted_once():
    producer = _FakeProducer(ack=True)
    pub = _publisher(producer)

    await pub._publish_single(_Event(), "test-topic")

    assert pub.metrics.events_published == 1


@pytest.mark.asyncio
async def test_slow_acknowledgement_is_still_awaited():
    """Delivery confirmation must not be skipped just because it is slow."""
    producer = _FakeProducer(ack=True, ack_delay=0.05)
    pub = _publisher(producer)

    result = await pub._publish_single(_Event(), "test-topic")

    assert result is True
    assert producer.acknowledged == ["test-topic"]


# ---------------------------------------------------------------------------
# Batch flush must account for loss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_flush_records_failures_in_metrics():
    """
    Events lost during a flush must be counted. Previously the exception was
    caught and discarded, so loss was invisible.
    """
    producer = _FakeProducer(error=RuntimeError("broker down"))
    pub = _publisher(producer, max_batch_size=10)

    pub._pending_events["test-topic"] = [_Event(f"evt-{i}") for i in range(3)]
    await pub._flush_topic_batch("test-topic")

    assert pub.metrics.events_failed == 3, (
        "All three undelivered events must be recorded as failures."
    )
    assert pub.metrics.events_published == 0


@pytest.mark.asyncio
async def test_batch_flush_succeeds_when_broker_acknowledges():
    producer = _FakeProducer(ack=True)
    pub = _publisher(producer, max_batch_size=10)

    pub._pending_events["test-topic"] = [_Event(f"evt-{i}") for i in range(3)]
    await pub._flush_topic_batch("test-topic")

    assert pub.metrics.events_published == 3
    assert pub.metrics.events_failed == 0
    assert len(producer.acknowledged) == 3


@pytest.mark.asyncio
async def test_batch_flush_clears_buffer_without_requeue():
    """
    Failed events must NOT be pushed back into the in-memory buffer: on a
    sustained outage that grows without bound (the ENH-007 failure mode).
    """
    producer = _FakeProducer(error=RuntimeError("broker down"))
    pub = _publisher(producer, max_batch_size=10)

    pub._pending_events["test-topic"] = [_Event(f"evt-{i}") for i in range(3)]
    await pub._flush_topic_batch("test-topic")

    assert pub._pending_events["test-topic"] == []


@pytest.mark.asyncio
async def test_partial_batch_failure_is_attributable():
    """A mixed batch must report exactly which events were lost."""

    class _FlakyProducer(_FakeProducer):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def send(self, topic, value, partition=None, key=None):
            self.calls += 1
            fail = self.calls == 2
            self.sent.append({"topic": topic})

            async def _delivery():
                if fail:
                    raise RuntimeError("partition unavailable")
                self.acknowledged.append(topic)
                return _RecordMetadata()

            return asyncio.ensure_future(_delivery())

    producer = _FlakyProducer()
    pub = _publisher(producer, max_batch_size=10)

    pub._pending_events["test-topic"] = [_Event(f"evt-{i}") for i in range(3)]
    await pub._flush_topic_batch("test-topic")

    assert pub.metrics.events_published == 2
    assert pub.metrics.events_failed == 1


# ---------------------------------------------------------------------------
# Non-awaitable tolerance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_awaitable_delivery_result_is_tolerated():
    """Some driver versions/doubles return a value rather than a future."""

    class _SyncProducer(_FakeProducer):
        async def send(self, topic, value, partition=None, key=None):
            self.sent.append({"topic": topic})
            return _RecordMetadata()

    pub = _publisher(_SyncProducer())
    assert await pub._publish_single(_Event(), "test-topic") is True


@pytest.mark.asyncio
async def test_none_delivery_result_is_tolerated():
    class _NoneProducer(_FakeProducer):
        async def send(self, topic, value, partition=None, key=None):
            self.sent.append({"topic": topic})
            return None

    pub = _publisher(_NoneProducer())
    assert await pub._publish_single(_Event(), "test-topic") is True
