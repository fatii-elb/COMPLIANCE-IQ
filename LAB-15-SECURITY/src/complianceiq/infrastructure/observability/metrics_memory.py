"""In-memory metrics sink with a Prometheus text renderer (offline default).

Implements the :class:`MetricsSink` port with plain dicts: monotonic **counters**
and lightweight **summaries** (count / sum / min / max) per label set. It renders
the standard Prometheus text exposition format so a ``GET /metrics`` endpoint can
be scraped, and exposes a structured :meth:`snapshot` for tests and JSON views.

Process-local and dependency-free — the whole system stays observable and testable
offline. A real exporter (OpenTelemetry/Prometheus client) implements the same
port later without touching callers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from threading import Lock

from complianceiq.domain.ports.metrics import MetricsSink

#: A metric series key: the metric name plus its sorted label pairs.
_Key = tuple[str, tuple[tuple[str, str], ...]]


def _key(name: str, labels: dict[str, str]) -> _Key:
    return name, tuple(sorted(labels.items()))


@dataclass
class _Summary:
    """A minimal value distribution: count, sum, min, max."""

    count: int = 0
    total: float = 0.0
    minimum: float = math.inf
    maximum: float = -math.inf

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)

    @property
    def mean(self) -> float:
        return self.total / self.count if self.count else 0.0


@dataclass
class InMemoryMetrics(MetricsSink):
    """Aggregates counters and summaries; renders Prometheus text."""

    _counters: dict[_Key, float] = field(default_factory=dict)
    _summaries: dict[_Key, _Summary] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = _key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = _key(name, labels)
        with self._lock:
            self._summaries.setdefault(key, _Summary()).observe(value)

    # ------------------------------------------------------------- read views

    def snapshot(self) -> dict[str, object]:
        """Return a structured snapshot of all series (for JSON / tests)."""
        with self._lock:
            counters = [
                {"name": name, "labels": dict(labels), "value": value}
                for (name, labels), value in sorted(self._counters.items())
            ]
            summaries = [
                {
                    "name": name,
                    "labels": dict(labels),
                    "count": s.count,
                    "sum": round(s.total, 4),
                    "min": None if s.count == 0 else round(s.minimum, 4),
                    "max": None if s.count == 0 else round(s.maximum, 4),
                    "mean": round(s.mean, 4),
                }
                for (name, labels), s in sorted(self._summaries.items())
            ]
        return {"counters": counters, "summaries": summaries}

    def render_prometheus(self) -> str:
        """Render all series in the Prometheus text exposition format."""
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"{name}{_labels_text(labels)} {_num(value)}")
            for (name, labels), s in sorted(self._summaries.items()):
                base = _labels_text(labels)
                lines.append(f"{name}_count{base} {s.count}")
                lines.append(f"{name}_sum{base} {_num(s.total)}")
                if s.count:
                    lines.append(f"{name}_min{base} {_num(s.minimum)}")
                    lines.append(f"{name}_max{base} {_num(s.maximum)}")
        return "\n".join(lines) + ("\n" if lines else "")


def _labels_text(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in labels)
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _num(value: float) -> str:
    # Render whole numbers without a trailing ".0" for clean exposition.
    return str(int(value)) if float(value).is_integer() else repr(value)
