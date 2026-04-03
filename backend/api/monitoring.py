from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth import get_current_active_user
from database import User
from schemas.response import success_response
from src.evolution.monitoring_service import monitoring_service


router = APIRouter()


@router.get("/")
async def get_monitoring_summary(
    current_user: User = Depends(get_current_active_user),
):
    """Get overall monitoring summary and active alerts."""
    return success_response(data=monitoring_service.get_summary())


@router.get("/health")
async def get_monitoring_health(
    current_user: User = Depends(get_current_active_user),
):
    """Get model health status map."""
    return success_response(data=monitoring_service.get_health_status())


@router.get("/metrics")
async def get_monitoring_metrics(
    model_name: Optional[str] = Query(default=None, description="可选模型名"),
    current_user: User = Depends(get_current_active_user),
):
    """Get all model metrics or one model's metrics."""
    return success_response(data=monitoring_service.get_metrics(model_name))


@router.get("/alerts")
async def get_monitoring_alerts(
    include_resolved: bool = Query(default=False, description="是否包含已恢复告警"),
    limit: int = Query(default=100, ge=1, le=500, description="返回数量上限"),
    current_user: User = Depends(get_current_active_user),
):
    """Get active alerts by default, or include resolved alerts."""
    alerts = monitoring_service.get_alerts(include_resolved=include_resolved, limit=limit)
    return success_response(data=alerts)


@router.post("/alerts/test")
async def create_monitoring_test_alert(
    current_user: User = Depends(get_current_active_user),
):
    """Create a manual test alert for validation."""
    alert = monitoring_service.create_test_alert(triggered_by=str(current_user.id))
    return success_response(data=alert, message="测试告警已创建")
