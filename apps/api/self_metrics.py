"""
Self-observability: RED metrics in Prometheus exposition format (ENH-019).

An observability platform that cannot observe itself is a credibility problem
as much as an operational one. Before this module there was no `/metrics`
endpoint anywhere, and the counters that DID exist (`EventMetrics`,
`BufferStats`) were accumulated in memory and never exported -- so an on-call
engineer had only logs, with no ingest lag, queue depth, error rate or latency
percentiles.

Deliberately dependency-free
----------------------------
This writes the Prometheus text exposition format directly rather than adding
`prometheus_client`. The format is stable and simple, and avoiding a new runtime
dependency keeps this change surgical -- `apps/api/requirements.txt` is already
pinned and unaudited (see the ENH-011 dependency-scan job). If richer primitives
(exemplars, native histograms) are needed later, swapping in the official client
is a contained change behind this module's API.

Histograms use fixed buckets chosen for API latency (1ms .. 10s).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

# Latency buckets in seconds. Chosen to give resolution where API latency
# actually lives, with a long tail for pathological queries.
DEFAULT_BUCKETS: Tuple[float, ...] = (
    0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
)

LabelKey = Tuple[Tuple[str, str], ...]


def _labels_to_key(labels: Optional[Dict[str, str]]) -> LabelKey:
    if not labels:
        return ()
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


def _escape(value: str) -> str:
    """Escape a label value per the Prometheus text format."""
    return (
        value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    )


def _render_labels(key: LabelKey) -> str:
    if not key:
        return ""
    inner = ",".join(f'{name}="{_escape(value)}"' for name, value in key)
    return "{" + inner + "}"


class MetricsRegistry:
    """
    A minimal, thread-safe metrics registry.

    Thread safety matters here: metrics are updated from request handlers, from
    the write-buffer's background flush loop, and from the daemon threads the
    ingest path still spawns (ENH-009).
    """

    def __init__(self, buckets: Iterable[float] = DEFAULT_BUCKETS):
        self._lock = threading.Lock()
        self._counters: Dict[str, Dict[LabelKey, float]] = defaultdict(dict)
        self._gauges: Dict[str, Dict[LabelKey, float]] = defaultdict(dict)
        self._histograms: Dict[str, Dict[LabelKey, List[float]]] = defaultdict(dict)
        self._help: Dict[str, str] = {}
        self._buckets = tuple(sorted(buckets))

    # -- registration ----------------------------------------------------

    def describe(self, name: str, help_text: str) -> None:
        with self._lock:
            self._help[name] = help_text

    # -- writes ----------------------------------------------------------

    def inc(self, name: str, value: float = 1.0,
            labels: Optional[Dict[str, str]] = None) -> None:
        key = _labels_to_key(labels)
        with self._lock:
            series = self._counters[name]
            series[key] = series.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None) -> None:
        key = _labels_to_key(labels)
        with self._lock:
            self._gauges[name][key] = float(value)

    def add_gauge(self, name: str, delta: float,
                  labels: Optional[Dict[str, str]] = None) -> None:
        key = _labels_to_key(labels)
        with self._lock:
            series = self._gauges[name]
            series[key] = series.get(key, 0.0) + float(delta)

    def observe(self, name: str, value: float,
                labels: Optional[Dict[str, str]] = None) -> None:
        key = _labels_to_key(labels)
        with self._lock:
            series = self._histograms[name]
            if key not in series:
                # bucket counts + [sum, count]
                series[key] = [0.0] * (len(self._buckets) + 2)

            slot = series[key]
            for index, bound in enumerate(self._buckets):
                if value <= bound:
                    slot[index] += 1
            slot[-2] += value  # sum
            slot[-1] += 1      # count

    # -- read ------------------------------------------------------------

    def snapshot(self) -> Dict[str, Dict]:
        """A copy of current values, for tests and debugging."""
        with self._lock:
            return {
                "counters": {k: dict(v) for k, v in self._counters.items()},
                "gauges": {k: dict(v) for k, v in self._gauges.items()},
                "histograms": {
                    k: {ik: list(iv) for ik, iv in v.items()}
                    for k, v in self._histograms.items()
                },
            }

    def render(self) -> str:
        """Render all metrics in the Prometheus text exposition format."""
        lines: List[str] = []

        with self._lock:
            for name, series in sorted(self._counters.items()):
                if name in self._help:
                    lines.append(f"# HELP {name} {self._help[name]}")
                lines.append(f"# TYPE {name} counter")
                for key, value in sorted(series.items()):
                    lines.append(f"{name}{_render_labels(key)} {value}")

            for name, series in sorted(self._gauges.items()):
                if name in self._help:
                    lines.append(f"# HELP {name} {self._help[name]}")
                lines.append(f"# TYPE {name} gauge")
                for key, value in sorted(series.items()):
                    lines.append(f"{name}{_render_labels(key)} {value}")

            for name, series in sorted(self._histograms.items()):
                if name in self._help:
                    lines.append(f"# HELP {name} {self._help[name]}")
                lines.append(f"# TYPE {name} histogram")
                for key, slot in sorted(series.items()):
                    cumulative = 0.0
                    for index, bound in enumerate(self._buckets):
                        cumulative = slot[index]
                        bucket_key = key + (("le", str(bound)),)
                        lines.append(
                            f"{name}_bucket{_render_labels(bucket_key)} {cumulative}"
                        )
                    inf_key = key + (("le", "+Inf"),)
                    lines.append(
                        f"{name}_bucket{_render_labels(inf_key)} {slot[-1]}"
                    )
                    lines.append(f"{name}_sum{_render_labels(key)} {slot[-2]}")
                    lines.append(f"{name}_count{_render_labels(key)} {slot[-1]}")

        return "\n".join(lines) + "\n"


# Global registry
_registry: Optional[MetricsRegistry] = None


def get_registry() -> MetricsRegistry:
    """Get the process-wide metrics registry."""
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
        _describe_core_metrics(_registry)
    return _registry


def reset_registry() -> None:
    """Reset the registry (tests only)."""
    global _registry
    _registry = None


def _describe_core_metrics(registry: MetricsRegistry) -> None:
    registry.describe(
        "logforge_http_requests_total",
        "Total HTTP requests, by method, path template and status class.",
    )
    registry.describe(
        "logforge_http_request_duration_seconds",
        "HTTP request latency in seconds.",
    )
    registry.describe(
        "logforge_http_requests_in_flight",
        "HTTP requests currently being served.",
    )
    registry.describe(
        "logforge_write_buffer_logs_buffered",
        "Logs currently held in the write buffer (ENH-007).",
    )
    registry.describe(
        "logforge_write_buffer_dead_lettered_total",
        "Logs written to the dead-letter sink because the buffer was full or "
        "a flush failed. A rising value means the pipeline is shedding data.",
    )
    registry.describe(
        "logforge_events_published_total",
        "Events acknowledged by the broker (ENH-006).",
    )
    registry.describe(
        "logforge_events_failed_total",
        "Events the broker did not acknowledge. Any non-zero value is log loss.",
    )


# ---------------------------------------------------------------------------
# Request instrumentation
# ---------------------------------------------------------------------------


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


class MetricsMiddleware:
    """
    ASGI middleware recording RED metrics (Rate, Errors, Duration).

    Implemented at the raw ASGI layer rather than as a `BaseHTTPMiddleware` so
    that it adds no per-request task overhead on the hot path.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        registry = get_registry()
        method = scope.get("method", "UNKNOWN")
        # Provisional: the real route template is only known after routing has
        # run, so this is recomputed in the `finally` block below.
        path = self._route_template(scope)

        registry.add_gauge(
            "logforge_http_requests_in_flight", 1.0, {"method": method}
        )
        start = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            # Re-read the route template AFTER routing has run. Starlette
            # populates scope["route"] during dispatch, so reading it up front
            # (before `await self.app(...)`) always misses it and falls back to
            # the truncated path.
            path = self._route_template(scope) or path
            labels = {
                "method": method,
                "path": path,
                "status": _status_class(status_holder["code"]),
            }
            registry.inc("logforge_http_requests_total", 1.0, labels)
            registry.observe(
                "logforge_http_request_duration_seconds",
                duration,
                {"method": method, "path": path},
            )
            registry.add_gauge(
                "logforge_http_requests_in_flight", -1.0, {"method": method}
            )

    @staticmethod
    def _route_template(scope) -> str:
        """
        Use the matched ROUTE TEMPLATE, never the raw path.

        A raw path such as `/v1/tenants/abc-123` would create one time series
        per tenant id -- an unbounded-cardinality explosion, which is precisely
        the failure mode this product exists to help customers avoid.
        """
        route = scope.get("route")
        if route is not None and getattr(route, "path", None):
            return route.path

        raw = scope.get("path", "/")
        # Before routing has run there is no template. Keep only the first two
        # segments so cardinality stays bounded.
        segments = [s for s in raw.split("/") if s][:2]
        return "/" + "/".join(segments) if segments else "/"


def collect_pipeline_gauges() -> None:
    """
    Refresh gauges sourced from subsystem state.

    Called when `/metrics` is scraped so the values are fresh without needing a
    background poller.
    """
    registry = get_registry()

    try:
        from services.write_buffer_service import get_write_buffer

        stats = get_write_buffer().get_stats()
        registry.set_gauge(
            "logforge_write_buffer_logs_buffered",
            stats["current_state"]["logs_in_buffer"],
        )
        registry.set_gauge(
            "logforge_write_buffer_dead_lettered_total",
            stats["stats"]["logs_dead_lettered"],
        )
        registry.set_gauge(
            "logforge_write_buffer_flush_errors_total",
            stats["stats"]["flush_errors"],
        )
    except Exception:
        # Metrics collection must never break the metrics endpoint itself.
        # A missing subsystem simply contributes no series.
        pass

    try:
        # ENH-009: ingest pipeline saturation. Queue depth rising toward the
        # cap, or a non-zero drop count, is the earliest signal that ingest
        # cannot keep up.
        from ingest_pipeline import get_ingest_pipeline

        pipeline = get_ingest_pipeline().get_stats()
        registry.set_gauge("logforge_ingest_queue_depth", pipeline["queue_depth"])
        registry.set_gauge("logforge_ingest_queue_capacity", pipeline["queue_size"])
        registry.set_gauge(
            "logforge_ingest_dropped_total",
            pipeline["stats"]["dropped_queue_full"]
            + pipeline["stats"]["dropped_not_running"],
        )
        registry.set_gauge(
            "logforge_ingest_failed_total", pipeline["stats"]["failed"]
        )
    except Exception:
        pass

    try:
        import dependencies

        manager = getattr(dependencies, "event_publisher_manager", None)
        if manager is not None:
            for name, metrics in manager.get_metrics().items():
                registry.set_gauge(
                    "logforge_events_published_total",
                    metrics.get("events_published", 0),
                    {"publisher": name},
                )
                registry.set_gauge(
                    "logforge_events_failed_total",
                    metrics.get("events_failed", 0),
                    {"publisher": name},
                )
    except Exception:
        pass
