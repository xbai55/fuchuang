"""
Monitoring service that wraps model metrics and alert lifecycle.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Optional

from src.evolution.model_monitor import ModelMonitor


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alert_key(alert: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(alert.get("severity", "")),
            str(alert.get("model", "")),
            str(alert.get("rule", "")),
            str(alert.get("message", "")),
        ]
    )


class MonitoringService:
    """Application-level monitoring and alert state management."""

    def __init__(self, max_alert_history: int = 500):
        self.monitor = ModelMonitor()
        self._lock = RLock()
        self._active_alerts: Dict[str, Dict[str, Any]] = {}
        self._alert_history: List[Dict[str, Any]] = []
        self._max_alert_history = max_alert_history

    async def record_request(
        self,
        model_name: str,
        latency_ms: float,
        success: bool,
        error: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self.monitor.record_request(
            model_name=model_name,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )
        self.refresh_alerts()

    def refresh_alerts(self) -> None:
        with self._lock:
            latest_alerts = self.monitor.check_alerts()
            now = _now_iso()
            seen_keys: set[str] = set()

            for alert in latest_alerts:
                key = _alert_key(alert)
                seen_keys.add(key)

                if key in self._active_alerts:
                    record = self._active_alerts[key]
                    record["last_seen"] = now
                    record["occurrences"] = int(record.get("occurrences", 1)) + 1
                    record["latest"] = alert
                    continue

                record = {
                    "key": key,
                    "status": "active",
                    "first_seen": now,
                    "last_seen": now,
                    "occurrences": 1,
                    "latest": alert,
                }
                self._active_alerts[key] = record
                self._alert_history.append(dict(record))

            resolved_keys = [key for key in self._active_alerts.keys() if key not in seen_keys]
            for key in resolved_keys:
                record = self._active_alerts[key]
                if record.get("pinned"):
                    continue

                record = self._active_alerts.pop(key)
                record["status"] = "resolved"
                record["resolved_at"] = now
                self._alert_history.append(dict(record))

            self._alert_history = self._alert_history[-self._max_alert_history :]

    def get_summary(self) -> Dict[str, Any]:
        self.refresh_alerts()
        summary = self.monitor.get_summary()
        with self._lock:
            summary["active_alerts"] = len(self._active_alerts)
            summary["active_alert_list"] = list(self._active_alerts.values())
            summary["alert_history_size"] = len(self._alert_history)
        return summary

    def get_metrics(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        return self.monitor.get_metrics(model_name)

    def get_health_status(self) -> Dict[str, str]:
        return self.monitor.get_health_status()

    def get_alerts(self, include_resolved: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        self.refresh_alerts()
        with self._lock:
            if include_resolved:
                return list(reversed(self._alert_history))[:limit]
            return list(reversed(list(self._active_alerts.values())))[:limit]

    def create_test_alert(self, triggered_by: Optional[str] = None) -> Dict[str, Any]:
        now = _now_iso()
        payload = {
            "severity": "medium",
            "model": "monitoring.system",
            "rule": "manual_test",
            "metric": "manual",
            "value": 1.0,
            "threshold": 0.0,
            "message": "Manual test alert",
            "timestamp": now,
            "triggered_by": triggered_by,
        }
        key = _alert_key(payload) + f"|{now}"

        record = {
            "key": key,
            "status": "active",
            "first_seen": now,
            "last_seen": now,
            "occurrences": 1,
            "latest": payload,
            "pinned": True,
        }

        with self._lock:
            self._active_alerts[key] = record
            self._alert_history.append(dict(record))
            self._alert_history = self._alert_history[-self._max_alert_history :]

        return record


monitoring_service = MonitoringService()
