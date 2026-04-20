"""
Case ingestor for automated fraud case ingestion into vector database.
Handles new fraud cases from various sources.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from src.brain.knowledge_search import KnowledgeSearchService


@dataclass
class FraudCase:
    """Represents a fraud case for ingestion."""
    case_id: str
    title: str
    content: str
    case_type: str
    source: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class CaseIngestor:
    """
    Automated fraud case ingestor.

    Ingests new fraud cases into the vector database for RAG.
    Handles validation, embedding generation, and indexing.
    """

    def __init__(
        self,
        knowledge_service: Optional["KnowledgeSearchService"] = None,
    ):
        """
        Initialize case ingestor.

        Args:
            knowledge_service: Optional KnowledgeSearchService instance
        """
        self.knowledge_service = knowledge_service
        self._service_init_error: Optional[str] = None
        self._ingestion_log: List[Dict[str, Any]] = []

    def _create_knowledge_service(self) -> Optional["KnowledgeSearchService"]:
        """Create default knowledge service for real ingestion."""
        try:
            from src.brain.knowledge_search import KnowledgeSearchService

            self._service_init_error = None
            return KnowledgeSearchService()
        except Exception as exc:
            self._service_init_error = str(exc)
            return None

    def _get_knowledge_service(self) -> Optional["KnowledgeSearchService"]:
        """Reuse injected service or lazily create a default one."""
        if self.knowledge_service is None:
            self.knowledge_service = self._create_knowledge_service()
        return self.knowledge_service

    async def ingest(
        self,
        case: FraudCase,
    ) -> Dict[str, Any]:
        """
        Ingest a single fraud case.

        Args:
            case: Fraud case to ingest

        Returns:
            Ingestion result
        """
        # Validate case
        validation = self._validate_case(case)
        if not validation["valid"]:
            return {
                "success": False,
                "case_id": case.case_id,
                "error": validation["error"],
            }

        success = False
        error_message: Optional[str] = None

        try:
            # Ingest to knowledge base using a real service instance.
            knowledge_service = self._get_knowledge_service()
            if knowledge_service is None:
                error_message = "Knowledge service unavailable for automatic ingestion"
                if self._service_init_error:
                    error_message = f"{error_message}: {self._service_init_error}"
            else:
                success = await knowledge_service.ingest_case(
                    case_id=case.case_id,
                    title=case.title,
                    content=case.content,
                    case_type=case.case_type,
                    source=case.source,
                )
                if not success:
                    error_message = "Knowledge service ingest_case returned False"

        except Exception as e:
            error_message = str(e)

        # Log ingestion outcome for observability.
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "case_id": case.case_id,
            "case_type": case.case_type,
            "source": case.source,
            "success": success,
        }
        if error_message:
            log_entry["error"] = error_message
        self._ingestion_log.append(log_entry)

        response = {
            "success": success,
            "case_id": case.case_id,
            "timestamp": log_entry["timestamp"],
        }
        if error_message:
            response["error"] = error_message
        return response

    async def ingest_batch(
        self,
        cases: List[FraudCase],
    ) -> List[Dict[str, Any]]:
        """
        Ingest multiple fraud cases in batch.

        Args:
            cases: List of fraud cases

        Returns:
            List of ingestion results
        """
        results = []
        for case in cases:
            result = await self.ingest(case)
            results.append(result)
        return results

    def _validate_case(self, case: FraudCase) -> Dict[str, Any]:
        """
        Validate a fraud case before ingestion.

        Args:
            case: Fraud case to validate

        Returns:
            Validation result
        """
        if not case.case_id:
            return {"valid": False, "error": "Case ID is required"}

        if not case.title:
            return {"valid": False, "error": "Title is required"}

        if not case.content:
            return {"valid": False, "error": "Content is required"}

        if len(case.content) < 10:
            return {"valid": False, "error": "Content is too short"}

        if not case.case_type:
            return {"valid": False, "error": "Case type is required"}

        return {"valid": True}

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """
        Get ingestion statistics.

        Returns:
            Statistics dictionary
        """
        total = len(self._ingestion_log)
        successful = sum(1 for log in self._ingestion_log if log.get("success"))

        return {
            "total_ingested": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0,
        }

    def get_ingestion_log(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get ingestion log.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of log entries
        """
        return self._ingestion_log[-limit:]

    async def ingest_from_detection_result(
        self,
        user_id: str,
        risk_score: int,
        scam_type: str,
        content: str,
        confirmed_fraud: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest a case from a detection result (evolution pipeline).

        Args:
            user_id: User ID
            risk_score: Risk score
            scam_type: Scam type
            content: Case content
            confirmed_fraud: Whether fraud was confirmed

        Returns:
            Ingestion result
        """
        case = FraudCase(
            case_id=f"auto_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}",
            title=f"{scam_type}案例 (自动收录)",
            content=content,
            case_type=scam_type,
            source="auto_detection",
            timestamp=datetime.now(),
            metadata={
                "risk_score": risk_score,
                "confirmed": confirmed_fraud,
                "user_id": user_id,
            },
        )

        return await self.ingest(case)
