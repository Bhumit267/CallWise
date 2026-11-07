"""Prometheus-compatible observability metrics collector for Callwise."""

from collections import defaultdict
import threading
import time
from typing import Dict, Optional, Tuple

from callwise.agent.circuit_breaker import CircuitState, circuit_breaker


class MetricsRegistry:
    """Thread-safe Prometheus metrics collector and exposition renderer."""

    def __init__(self):
        self._lock = threading.Lock()

        # Counters: (name, label_tuple) -> float
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)

        # Gauges: (name, label_tuple) -> float
        self._gauges: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)

        # Summaries / Histograms: (name, label_tuple) -> [count, sum]
        self._summaries: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], list] = defaultdict(lambda: [0, 0.0])

    def inc_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a metric counter."""
        label_tuple = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            self._counters[(name, label_tuple)] += value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a metric gauge to a specific value."""
        label_tuple = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            self._gauges[(name, label_tuple)] = value

    def observe_summary(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Observe a duration or measurement for summary statistics."""
        label_tuple = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            entry = self._summaries[(name, label_tuple)]
            entry[0] += 1
            entry[1] += float(value)

    def track_call(self, status: str, session_type: str = "phone", duration_seconds: float = 0.0) -> None:
        """Record completed or ongoing call event."""
        self.inc_counter("callwise_calls_total", 1.0, {"status": status, "session_type": session_type})
        if duration_seconds > 0:
            self.observe_summary("callwise_call_duration_seconds", duration_seconds, {"session_type": session_type})

    def track_llm_turn(self, provider: str, status: str = "success", latency_seconds: float = 0.0) -> None:
        """Record LLM inference interaction turn."""
        self.inc_counter("callwise_llm_turns_total", 1.0, {"provider": provider, "status": status})
        if latency_seconds > 0:
            self.observe_summary("callwise_llm_latency_seconds", latency_seconds, {"provider": provider})

    def track_abuse_event(self, reason: str) -> None:
        """Record blocked abuse or flood detection event."""
        self.inc_counter("callwise_abuse_events_total", 1.0, {"reason": reason})

    def track_rate_limit(self, limit_type: str) -> None:
        """Record rate limit hit."""
        self.inc_counter("callwise_rate_limits_hit_total", 1.0, {"type": limit_type})

    def track_usage_cost(self, cost_usd: float) -> None:
        """Track estimated cumulative telephony and AI infrastructure cost."""
        if cost_usd > 0:
            self.inc_counter("callwise_usage_cost_usd_total", cost_usd)

    def render_prometheus(self) -> str:
        """Export all registered metrics in standard Prometheus exposition format."""
        lines = []

        # Update dynamic circuit breaker gauges
        state_map = {
            CircuitState.CLOSED: 0.0,
            CircuitState.HALF_OPEN: 1.0,
            CircuitState.OPEN: 2.0,
        }
        for provider in ("groq", "gemini", "ollama"):
            circuit = circuit_breaker.get_circuit(provider)
            self.set_gauge("callwise_circuit_breaker_state", state_map.get(circuit.state, 0.0), {"provider": provider})

        with self._lock:
            # 1. Counters
            counters_by_name = defaultdict(list)
            for (name, labels), val in self._counters.items():
                counters_by_name[name].append((labels, val))

            for name, items in sorted(counters_by_name.items()):
                lines.append(f"# TYPE {name} counter")
                for labels, val in sorted(items):
                    lbl_str = ""
                    if labels:
                        lbl_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels) + "}"
                    lines.append(f"{name}{lbl_str} {val}")

            # 2. Gauges
            gauges_by_name = defaultdict(list)
            for (name, labels), val in self._gauges.items():
                gauges_by_name[name].append((labels, val))

            for name, items in sorted(gauges_by_name.items()):
                lines.append(f"# TYPE {name} gauge")
                for labels, val in sorted(items):
                    lbl_str = ""
                    if labels:
                        lbl_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels) + "}"
                    lines.append(f"{name}{lbl_str} {val}")

            # 3. Summaries
            summaries_by_name = defaultdict(list)
            for (name, labels), (count, total_sum) in self._summaries.items():
                summaries_by_name[name].append((labels, count, total_sum))

            for name, items in sorted(summaries_by_name.items()):
                lines.append(f"# TYPE {name} summary")
                for labels, count, total_sum in sorted(items):
                    lbl_base = ",".join(f'{k}="{v}"' for k, v in labels) if labels else ""
                    lbl_count = "{" + (lbl_base + "," if lbl_base else "") + 'quantile="count"}' if lbl_base else ""
                    lbl_sum = "{" + (lbl_base + "," if lbl_base else "") + 'quantile="sum"}' if lbl_base else ""
                    lines.append(f"{name}_count{lbl_count} {count}")
                    lines.append(f"{name}_sum{lbl_sum} {total_sum:.4f}")

        return "\n".join(lines) + "\n"


# Global metrics registry singleton
metrics = MetricsRegistry()

