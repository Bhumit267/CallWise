"""Callwise Concurrency & Load Testing Script.

Simulates concurrent telephone calls, chat sessions, and API traffic.
Measures throughput (RPS), error rates, rate-limiting, and latency percentiles (p50, p90, p95, p99).
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from math import ceil
from pathlib import Path
import statistics
import time
from typing import Any, Dict, List, Optional
import httpx
from tabulate import tabulate

logger = logging.getLogger("callwise.load_test")


class LoadTestResult:
    """Aggregated load test execution statistics."""

    def __init__(
        self,
        target_url: str,
        total_requests: int,
        concurrency: int,
        duration_seconds: float,
        latencies_ms: List[float],
        status_counts: Dict[int, int],
        error_count: int,
        rate_limited_count: int,
    ):
        self.target_url = target_url
        self.total_requests = total_requests
        self.concurrency = concurrency
        self.duration_seconds = duration_seconds
        self.latencies_ms = sorted(latencies_ms)
        self.status_counts = status_counts
        self.error_count = error_count
        self.rate_limited_count = rate_limited_count
        self.rps = (total_requests / duration_seconds) if duration_seconds > 0 else 0.0

    def percentile(self, p: float) -> float:
        """Compute the p-th percentile of request latencies."""
        if not self.latencies_ms:
            return 0.0
        idx = min(len(self.latencies_ms) - 1, max(0, int(ceil(p * len(self.latencies_ms))) - 1))
        return self.latencies_ms[idx]

    @property
    def min_latency(self) -> float:
        return self.latencies_ms[0] if self.latencies_ms else 0.0

    @property
    def max_latency(self) -> float:
        return self.latencies_ms[-1] if self.latencies_ms else 0.0

    @property
    def mean_latency(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def median_latency(self) -> float:
        return self.percentile(0.50)

    @property
    def p90_latency(self) -> float:
        return self.percentile(0.90)

    @property
    def p95_latency(self) -> float:
        return self.percentile(0.95)

    @property
    def p99_latency(self) -> float:
        return self.percentile(0.99)

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to serializable dictionary."""
        return {
            "target_url": self.target_url,
            "total_requests": self.total_requests,
            "concurrency": self.concurrency,
            "duration_seconds": round(self.duration_seconds, 2),
            "requests_per_second": round(self.rps, 2),
            "status_codes": self.status_counts,
            "error_count": self.error_count,
            "rate_limited_count": self.rate_limited_count,
            "latency_ms": {
                "min": round(self.min_latency, 2),
                "mean": round(self.mean_latency, 2),
                "median_p50": round(self.median_latency, 2),
                "p90": round(self.p90_latency, 2),
                "p95": round(self.p95_latency, 2),
                "p99": round(self.p99_latency, 2),
                "max": round(self.max_latency, 2),
            },
        }

    def format_console(self) -> str:
        """Format results into clean ASCII summary tables."""
        output = []
        output.append("\n" + "=" * 65)
        output.append("          CALLWISE LOAD & CONCURRENCY TEST RESULTS          ")
        output.append("=" * 65)

        overview = [
            ["Target URL", self.target_url],
            ["Concurrency Level", self.concurrency],
            ["Total Requests", self.total_requests],
            ["Total Duration", f"{self.duration_seconds:.2f} s"],
            ["Throughput (RPS)", f"{self.rps:.2f} req/s"],
            ["Successful (2xx)", sum(c for code, c in self.status_counts.items() if 200 <= code < 300)],
            ["Rate Limited (429)", self.rate_limited_count],
            ["Errors / Failures", self.error_count],
        ]
        output.append("\n" + tabulate(overview, headers=["Configuration / Metric", "Value"], tablefmt="grid"))

        latency_table = [
            ["Minimum (Fastest)", f"{self.min_latency:.2f} ms"],
            ["Mean (Average)", f"{self.mean_latency:.2f} ms"],
            ["Median (p50)", f"{self.median_latency:.2f} ms"],
            ["90th Percentile (p90)", f"{self.p90_latency:.2f} ms"],
            ["95th Percentile (p95)", f"{self.p95_latency:.2f} ms"],
            ["99th Percentile (p99)", f"{self.p99_latency:.2f} ms"],
            ["Maximum (Slowest)", f"{self.max_latency:.2f} ms"],
        ]
        output.append("\n--- Latency Distribution ---")
        output.append(tabulate(latency_table, headers=["Percentile", "Latency (ms)"], tablefmt="grid"))

        status_rows = [[code, count] for code, count in sorted(self.status_counts.items())]
        output.append("\n--- HTTP Status Breakdown ---")
        output.append(tabulate(status_rows, headers=["Status Code", "Count"], tablefmt="grid") + "\n")

        return "\n".join(output)


async def run_load_test(
    url: str = "http://localhost:8000/api/health",
    total_requests: int = 50,
    concurrency: int = 5,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 10.0,
    client: Optional[httpx.AsyncClient] = None,
) -> LoadTestResult:
    """Execute asynchronous load test with worker queue pool."""
    latencies: List[float] = []
    status_counts: Dict[int, int] = {}
    error_count = 0
    rate_limited_count = 0

    queue: asyncio.Queue[int] = asyncio.Queue()
    for req_idx in range(total_requests):
        queue.put_nowait(req_idx)

    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
        should_close_client = True

    lock = asyncio.Lock()

    async def worker():
        nonlocal error_count, rate_limited_count
        while not queue.empty():
            try:
                _ = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            t0 = time.perf_counter()
            try:
                if method.upper() == "POST":
                    resp = await client.post(url, json=payload or {}, headers=headers)
                else:
                    resp = await client.get(url, headers=headers)
                dur_ms = (time.perf_counter() - t0) * 1000.0

                async with lock:
                    latencies.append(dur_ms)
                    code = resp.status_code
                    status_counts[code] = status_counts.get(code, 0) + 1
                    if code == 429:
                        rate_limited_count += 1
                    elif code >= 400:
                        error_count += 1
            except Exception as exc:
                dur_ms = (time.perf_counter() - t0) * 1000.0
                async with lock:
                    latencies.append(dur_ms)
                    error_count += 1
                    status_counts[599] = status_counts.get(599, 0) + 1
                    logger.debug(f"Request failed: {exc}")
            finally:
                queue.task_done()

    t_start = time.perf_counter()
    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*workers)
    t_elapsed = time.perf_counter() - t_start

    if should_close_client:
        await client.aclose()

    return LoadTestResult(
        target_url=url,
        total_requests=total_requests,
        concurrency=concurrency,
        duration_seconds=t_elapsed,
        latencies_ms=latencies,
        status_counts=status_counts,
        error_count=error_count,
        rate_limited_count=rate_limited_count,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Callwise Concurrency & Load Testing Tool")
    parser.add_argument("--url", default="http://localhost:8000/api/health", help="Target URL endpoint")
    parser.add_argument("-n", "--requests", type=int, default=50, help="Total number of requests")
    parser.add_argument("-c", "--concurrency", type=int, default=5, help="Number of concurrent workers")
    parser.add_argument("-m", "--method", default="GET", choices=["GET", "POST"], help="HTTP method")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="Request timeout in seconds")
    parser.add_argument("-o", "--output", help="Save JSON report to specified file path")

    args = parser.parse_args()

    print(f"Launching load test: {args.requests} requests to {args.url} (concurrency: {args.concurrency})...")
    res = asyncio.run(
        run_load_test(
            url=args.url,
            total_requests=args.requests,
            concurrency=args.concurrency,
            method=args.method,
            timeout=args.timeout,
        )
    )
    print(res.format_console())

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res.to_dict(), f, indent=2)
        print(f"[OK] Report saved to {out_path}")

