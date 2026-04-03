"""
Evolution layer for the anti-fraud system.
Handles automated case ingestion, feedback collection, and model monitoring.
"""
from src.evolution.case_ingestor import CaseIngestor
from src.evolution.feedback_collector import FeedbackCollector
from src.evolution.model_monitor import ModelMonitor
from src.evolution.monitoring_service import monitoring_service, MonitoringService
from src.evolution.runtime import EvolutionRuntime, get_evolution_runtime

__all__ = [
    "CaseIngestor",
    "FeedbackCollector",
    "ModelMonitor",
    "MonitoringService",
    "EvolutionRuntime",
    "get_evolution_runtime",
    "monitoring_service",
]
