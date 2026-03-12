"""Performance monitoring utilities."""
import time
import functools
from typing import Callable, Any
from loguru import logger
import asyncio


def measure_time(func: Callable) -> Callable:
    """Decorator to measure execution time of functions."""
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            if elapsed > 100:  # Log slow operations (>100ms)
                logger.warning(f"[perf] {func.__name__} took {elapsed:.2f}ms")
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(f"[perf] {func.__name__} failed after {elapsed:.2f}ms: {e}")
            raise

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            if elapsed > 100:  # Log slow operations (>100ms)
                logger.warning(f"[perf] {func.__name__} took {elapsed:.2f}ms")
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(f"[perf] {func.__name__} failed after {elapsed:.2f}ms: {e}")
            raise

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class PerformanceTracker:
    """Track performance metrics across the application."""

    def __init__(self):
        self.metrics = {}
        self.slow_queries = []

    def record_metric(self, name: str, value: float, unit: str = "ms"):
        """Record a performance metric."""
        if name not in self.metrics:
            self.metrics[name] = {
                "count": 0,
                "total": 0,
                "min": float('inf'),
                "max": 0,
                "unit": unit
            }

        metric = self.metrics[name]
        metric["count"] += 1
        metric["total"] += value
        metric["min"] = min(metric["min"], value)
        metric["max"] = max(metric["max"], value)

        # Track slow operations
        if unit == "ms" and value > 500:
            self.slow_queries.append({
                "name": name,
                "value": value,
                "timestamp": time.time()
            })
            # Keep only last 100 slow queries
            if len(self.slow_queries) > 100:
                self.slow_queries.pop(0)

    def get_summary(self):
        """Get performance summary."""
        summary = {}
        for name, data in self.metrics.items():
            if data["count"] > 0:
                summary[name] = {
                    "avg": data["total"] / data["count"],
                    "min": data["min"],
                    "max": data["max"],
                    "count": data["count"],
                    "unit": data["unit"]
                }
        return {
            "metrics": summary,
            "slow_queries": self.slow_queries[-10:]  # Last 10 slow queries
        }

    def reset(self):
        """Reset all metrics."""
        self.metrics.clear()
        self.slow_queries.clear()


# Global performance tracker instance
perf_tracker = PerformanceTracker()