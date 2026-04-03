"""
Utilities for personalized fraud-risk threshold calibration.
"""
from typing import Any, Dict, List, Tuple


DEFAULT_LOW_THRESHOLD = 40
DEFAULT_HIGH_THRESHOLD = 75

ROLE_THRESHOLD_OFFSETS = {
    "elderly": (-6, -6),
    "student": (-3, -3),
    "finance": (3, 3),
    "general": (0, 0),
}

MIN_LOW_THRESHOLD = 22
MAX_LOW_THRESHOLD = 65
MIN_HIGH_THRESHOLD = 45
MAX_HIGH_THRESHOLD = 95
MIN_THRESHOLD_GAP = 18


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_role(user_role: str) -> str:
    role = (user_role or "general").strip().lower()
    return role if role in ROLE_THRESHOLD_OFFSETS else "general"


def _clamp_thresholds(low_threshold: int, high_threshold: int) -> Tuple[int, int]:
    low = max(MIN_LOW_THRESHOLD, min(MAX_LOW_THRESHOLD, low_threshold))
    high = max(MIN_HIGH_THRESHOLD, min(MAX_HIGH_THRESHOLD, high_threshold))

    if high - low < MIN_THRESHOLD_GAP:
        high = min(MAX_HIGH_THRESHOLD, low + MIN_THRESHOLD_GAP)
        if high - low < MIN_THRESHOLD_GAP:
            low = max(MIN_LOW_THRESHOLD, high - MIN_THRESHOLD_GAP)

    return low, high


def risk_level_from_score(
    score: int,
    low_threshold: int = DEFAULT_LOW_THRESHOLD,
    high_threshold: int = DEFAULT_HIGH_THRESHOLD,
) -> str:
    if score > high_threshold:
        return "high"
    if score >= low_threshold:
        return "medium"
    return "low"


def build_personalized_thresholds(
    user_role: str,
    short_term_events: List[Dict[str, Any]] = None,
    history_profile: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Build personalized thresholds from user role, short-term events, and long-term history.

    Args:
        user_role: User role string (elderly/student/finance/general)
        short_term_events: Recent detections snapshots
        history_profile: Aggregated long-term history profile

    Returns:
        Dict containing thresholds and adjustment metadata
    """
    short_term_events = short_term_events or []
    history_profile = history_profile or {}

    low_threshold = DEFAULT_LOW_THRESHOLD
    high_threshold = DEFAULT_HIGH_THRESHOLD
    reasons: List[str] = []

    # Role-based baseline adjustment.
    normalized_role = _normalize_role(user_role)
    role_low_delta, role_high_delta = ROLE_THRESHOLD_OFFSETS[normalized_role]
    if role_low_delta or role_high_delta:
        low_threshold += role_low_delta
        high_threshold += role_high_delta
        reasons.append(f"角色({normalized_role})调整 {role_low_delta}/{role_high_delta}")

    # Short-term memory adjustment (recent risk trend).
    recent = list(short_term_events)[-5:]
    recent_scores = [_safe_int(item.get("risk_score"), 0) for item in recent]
    short_avg_score = (sum(recent_scores) / len(recent_scores)) if recent_scores else 0.0
    short_high_ratio = (
        sum(1 for score in recent_scores if score > DEFAULT_HIGH_THRESHOLD) / len(recent_scores)
        if recent_scores else 0.0
    )

    if recent_scores:
        if short_avg_score >= 72 or short_high_ratio >= 0.5:
            low_threshold -= 6
            high_threshold -= 6
            reasons.append("短期风险持续偏高")
        elif short_avg_score >= 58 or short_high_ratio >= 0.25:
            low_threshold -= 3
            high_threshold -= 3
            reasons.append("短期风险有上升迹象")
        elif len(recent_scores) >= 3 and short_avg_score <= 22 and short_high_ratio == 0:
            low_threshold += 2
            high_threshold += 2
            reasons.append("短期风险稳定偏低")

    # Long-term memory adjustment (historical behavior profile).
    long_total_count = _safe_int(history_profile.get("total_count"), 0)
    long_avg_score = _safe_float(history_profile.get("avg_score"), 0.0)
    long_high_ratio = _safe_float(history_profile.get("high_ratio"), 0.0)
    rising_risk = bool(history_profile.get("rising_risk", False))

    if long_total_count >= 8:
        if long_high_ratio >= 0.35 or long_avg_score >= 64:
            low_threshold -= 4
            high_threshold -= 4
            reasons.append("长期高风险占比偏高")
        elif long_high_ratio <= 0.08 and long_avg_score <= 24:
            low_threshold += 2
            high_threshold += 2
            reasons.append("长期风险整体偏低")

    if rising_risk:
        low_threshold -= 2
        high_threshold -= 2
        reasons.append("近期长期窗口风险抬升")

    low_threshold, high_threshold = _clamp_thresholds(low_threshold, high_threshold)

    return {
        "low_threshold": low_threshold,
        "high_threshold": high_threshold,
        "base_low_threshold": DEFAULT_LOW_THRESHOLD,
        "base_high_threshold": DEFAULT_HIGH_THRESHOLD,
        "adjustment_reasons": reasons,
        "signals": {
            "short_term_count": len(recent_scores),
            "short_term_avg_score": round(short_avg_score, 2),
            "short_term_high_ratio": round(short_high_ratio, 3),
            "long_term_total_count": long_total_count,
            "long_term_avg_score": round(long_avg_score, 2),
            "long_term_high_ratio": round(long_high_ratio, 3),
            "rising_risk": rising_risk,
        },
    }
