"""
Model monitor for tracking performance and detecting drift.
Monitors the anti-fraud system models.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import deque


@dataclass
class ModelMetrics:
    """Metrics for a single model."""
    model_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    last_check: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)


class ModelMonitor:
    """
    Monitor model performance and health.

    Tracks:
    - Request latency
    - Success/failure rates
    - Error patterns
    - Performance degradation
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize model monitor.

        Args:
            max_history: Maximum number of historical records to keep
        """
        self._metrics: Dict[str, ModelMetrics] = {}
        self._latency_history: Dict[str, deque] = {}
        self._max_history = max_history

    async def record_request(
        self,
        model_name: str,
        latency_ms: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        Record a model request.

        Args:
            model_name: Name of the model
            latency_ms: Request latency in milliseconds
            success: Whether the request succeeded
            error: Error message if failed
        """
        # Initialize metrics if needed
        if model_name not in self._metrics:
            self._metrics[model_name] = ModelMetrics(model_name=model_name)
            self._latency_history[model_name] = deque(maxlen=self._max_history)

        metrics = self._metrics[model_name]
        metrics.total_requests += 1

        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1
            if error:
                metrics.errors.append(f"{datetime.now().isoformat()}: {error}")
                # Keep only recent errors
                metrics.errors = metrics.errors[-100:]

        # Record latency
        self._latency_history[model_name].append(latency_ms)

        # Update latency statistics
        latencies = list(self._latency_history[model_name])
        if latencies:
            metrics.avg_latency_ms = sum(latencies) / len(latencies)
            metrics.p95_latency_ms = self._calculate_p95(latencies)

        metrics.last_check = datetime.now()

    def _calculate_p95(self, values: List[float]) -> float:
        """
        Calculate 95th percentile.

        Args:
            values: List of values

        Returns:
            95th percentile value
        """
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * 0.95)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_metrics(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for a model or all models.

        Args:
            model_name: Optional model name to filter

        Returns:
            Metrics dictionary
        """
        if model_name:
            metrics = self._metrics.get(model_name)
            if not metrics:
                return {}
            return self._format_metrics(metrics)

        return {
            name: self._format_metrics(m)
            for name, m in self._metrics.items()
        }

    def _format_metrics(self, metrics: ModelMetrics) -> Dict[str, Any]:
        """
        Format metrics for output.

        Args:
            metrics: ModelMetrics object

        Returns:
            Formatted dictionary
        """
        total = metrics.total_requests

        return {
            "model_name": metrics.model_name,
            "total_requests": total,
            "success_rate": metrics.successful_requests / total if total > 0 else 0,
            "avg_latency_ms": round(metrics.avg_latency_ms, 2),
            "p95_latency_ms": round(metrics.p95_latency_ms, 2),
            "last_check": metrics.last_check.isoformat() if metrics.last_check else None,
            "recent_errors": metrics.errors[-5:] if metrics.errors else [],
        }

    def get_health_status(self) -> Dict[str, str]:
        """
        Get health status for all models.

        Returns:
            Dict mapping model name to health status
        """
        status = {}

        for name, metrics in self._metrics.items():
            # Determine health status
            if metrics.total_requests == 0:
                status[name] = "unknown"
            elif metrics.failed_requests / metrics.total_requests > 0.1:
                status[name] = "degraded"
            elif metrics.p95_latency_ms > 5000:  # 5 seconds
                status[name] = "slow"
            else:
                status[name] = "healthy"

        return status

    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check for alert conditions.

        Returns:
            List of alerts
        """
        alerts = []

        for name, metrics in self._metrics.items():
            # Check error rate
            if metrics.total_requests > 0:
                error_rate = metrics.failed_requests / metrics.total_requests
                if error_rate > 0.2:
                    alerts.append({
                        "severity": "high",
                        "model": name,
                        "message": f"High error rate: {error_rate:.1%}",
                        "timestamp": datetime.now().isoformat(),
                    })

            # Check latency
            if metrics.p95_latency_ms > 8000:  # 8 seconds
                alerts.append({
                    "severity": "medium",
                    "model": name,
                    "message": f"High P95 latency: {metrics.p95_latency_ms:.0f}ms",
                    "timestamp": datetime.now().isoformat(),
                })

            # Check staleness
            if metrics.last_check:
                stale_threshold = timedelta(minutes=30)
                if datetime.now() - metrics.last_check > stale_threshold:
                    alerts.append({
                        "severity": "low",
                        "model": name,
                        "message": "No recent requests",
                        "timestamp": datetime.now().isoformat(),
                    })

        return alerts

    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall system summary.

        Returns:
            Summary dictionary
        """
        total_requests = sum(m.total_requests for m in self._metrics.values())
        total_success = sum(m.successful_requests for m in self._metrics.values())

        all_latencies = []
        for history in self._latency_history.values():
            all_latencies.extend(history)

        return {
            "total_models": len(self._metrics),
            "total_requests": total_requests,
            "overall_success_rate": total_success / total_requests if total_requests > 0 else 0,
            "overall_avg_latency_ms": round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else 0,
            "health_status": self.get_health_status(),
            "active_alerts": len(self.check_alerts()),
        }
