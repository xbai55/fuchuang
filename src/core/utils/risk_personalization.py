"""
Utilities for personalized fraud-risk calibration and multi-dimensional personas.
"""
from typing import Any, Dict, List, Tuple


DEFAULT_LOW_THRESHOLD = 40
DEFAULT_HIGH_THRESHOLD = 75
GENERAL_ROLE = "general"
UNKNOWN_VALUE = "unknown"

AGE_ALIASES = {
    "child": "child",
    "children": "child",
    "kid": "child",
    "\u513f\u7ae5": "child",
    "young_adult": "young_adult",
    "adult": "young_adult",
    "youth": "young_adult",
    "\u9752\u58ee\u5e74": "young_adult",
    "elderly": "elderly",
    "senior": "elderly",
    "\u8001\u4eba": "elderly",
    "\u8001\u5e74": "elderly",
    "\u8001\u5e74\u4eba": "elderly",
}

GENDER_ALIASES = {
    "male": "male",
    "man": "male",
    "\u7537": "male",
    "\u7537\u6027": "male",
    "female": "female",
    "woman": "female",
    "\u5973": "female",
    "\u5973\u6027": "female",
}

OCCUPATION_ALIASES = {
    "student": "student",
    "\u5b66\u751f": "student",
    "enterprise_staff": "enterprise_staff",
    "\u4f01\u4e1a\u804c\u5458": "enterprise_staff",
    "self_employed": "self_employed",
    "\u4e2a\u4f53\u7ecf\u8425": "self_employed",
    "\u4e2a\u4f53\u6237": "self_employed",
    "retired_group": "retired_group",
    "\u9000\u4f11\u7fa4\u4f53": "retired_group",
    "\u9000\u4f11": "retired_group",
    "public_officer": "public_officer",
    "\u516c\u804c\u4eba\u5458": "public_officer",
    "finance_practitioner": "finance_practitioner",
    "\u91d1\u878d\u4ece\u4e1a\u8005": "finance_practitioner",
    "\u91d1\u878d\u4ece\u4e1a": "finance_practitioner",
    "other": "other",
    "\u5176\u4ed6\u804c\u4e1a": "other",
}

ROLE_ALIASES = {
    GENERAL_ROLE: GENERAL_ROLE,
    "default": GENERAL_ROLE,
    "normal": GENERAL_ROLE,
    "common": GENERAL_ROLE,
    "elderly": "elderly",
    "senior": "elderly",
    "child": "child",
    "children": "child",
    "young_adult": "young_adult",
    "adult": "young_adult",
    "student": "student",
    "male": "male",
    "female": "female",
    "enterprise_staff": "enterprise_staff",
    "service_worker": "enterprise_staff",
    "self_employed": "self_employed",
    "freelancer": "self_employed",
    "retired_group": "retired_group",
    "public_officer": "public_officer",
    "finance_practitioner": "finance_practitioner",
    "finance": "finance_practitioner",
    "other": "other",
}

AGE_THRESHOLD_OFFSETS = {
    "child": (-8, -8),
    "young_adult": (-1, -1),
    "elderly": (-6, -6),
    UNKNOWN_VALUE: (0, 0),
}

GENDER_THRESHOLD_OFFSETS = {
    "male": (0, 0),
    "female": (-1, -1),
    UNKNOWN_VALUE: (0, 0),
}

OCCUPATION_THRESHOLD_OFFSETS = {
    "student": (-4, -4),
    "enterprise_staff": (-1, -1),
    "self_employed": (-3, -3),
    "retired_group": (-5, -5),
    "public_officer": (-2, -2),
    "finance_practitioner": (2, 2),
    "other": (0, 0),
}

COMPOSITE_PROFILE_MAP: Dict[Tuple[str, str, str], Dict[str, str]] = {
    ("child", UNKNOWN_VALUE, "student"): {
        "risk_level": "high",
        "risk_assessment": "High risk for game trading, fake fandom tasks, and anti-addiction bypass scams. Children may be induced to operate a parent's phone.",
        "prompt": "Gaming top-up or account-unlock requests are scams. Never share a parent's password, payment code, or OTP.",
    },
    ("young_adult", "female", "enterprise_staff"): {
        "risk_level": "medium",
        "risk_assessment": "Common targets include fake customer-service refunds and fake brushing-job offers, often using urgency and income pressure.",
        "prompt": "Official customer service will not ask for private transfers. Brushing jobs are traps. Close remote-control software immediately.",
    },
    ("young_adult", "male", "finance_practitioner"): {
        "risk_level": "medium",
        "risk_assessment": "Often targeted by fake high-yield investment platforms and romance-investment schemes exploiting professional confidence.",
        "prompt": "Reject any off-platform internal investment. Verify counterpart identity before any transfer or account funding.",
    },
    ("young_adult", "male", "self_employed"): {
        "risk_level": "high",
        "risk_assessment": "Common risks are fake loans, fake police-account anomalies, and fraud around business transfers and cash-flow stress.",
        "prompt": "Any loan requiring upfront fees is a scam. Verify business transfers by voice or offline confirmation first.",
    },
    ("young_adult", "female", "student"): {
        "risk_level": "high",
        "risk_assessment": "Common risks include campus-loan traps, fake credit-fix narratives, and brushing scams exploiting fear of credit damage.",
        "prompt": "Credit repair and safe-account transfers are scams. Stop and verify with school staff or family first.",
    },
    ("young_adult", UNKNOWN_VALUE, "public_officer"): {
        "risk_level": "medium",
        "risk_assessment": "Common risks include phishing emails, fake leadership transfer requests, and impersonation of discipline or law-enforcement bodies.",
        "prompt": "Urgent transfer requests from leaders on social apps must be confirmed offline. Do not open unknown links or attachments.",
    },
    ("elderly", "female", "retired_group"): {
        "risk_level": "high",
        "risk_assessment": "Common risks include impersonating children in emergencies and fake elder-care investments exploiting emotional pressure and retirement savings concerns.",
        "prompt": "If someone says your child is in trouble and needs money, hang up and call family directly before doing anything else.",
    },
    ("elderly", "male", "retired_group"): {
        "risk_level": "high",
        "risk_assessment": "Common risks include health-product fraud, fake prizes, and fake experts abusing trust in authority.",
        "prompt": "Miracle medicine and prize-handling fees are scams. Ask family before paying for any health product or fee.",
    },
}

OCCUPATION_PROFILE_MAP: Dict[str, Dict[str, str]] = {
    "elderly": {
        "label": "elderly",
        "tone": "warm, simple, step-by-step",
        "focus": "authority-pressure scams, family-emergency money requests, pension and health-product fraud",
        "education": "call family directly before transfers and avoid unknown investment or health products",
    },
    "child": {
        "label": "child",
        "tone": "short, direct, easy to understand",
        "focus": "game trading, fake school identity, QR-code prizes, and payment password theft",
        "education": "ask parents first and never use a parent's phone for stranger-guided payments",
    },
    "young_adult": {
        "label": "young_adult",
        "tone": "direct, efficient, action-oriented",
        "focus": "job scams, brushing orders, fake customer service, and investment lures",
        "education": "verify through official channels and slow down before transfers",
    },
    "male": {
        "label": "male",
        "tone": "concise, rational, verification-first",
        "focus": "high-return investment scams, gambling rebates, and fake friend borrowing",
        "education": "do not skip verification because of confidence in your own judgment",
    },
    "female": {
        "label": "female",
        "tone": "clear, calm, detail-aware",
        "focus": "emotional manipulation, fake customer service, and social-relation scams",
        "education": "verify identity and protect privacy before responding to pressure or emotional stories",
    },
    "student": {
        "label": "student",
        "tone": "friendly, direct, practical",
        "focus": "campus loans, brushing orders, game trading, fake account cancellation",
        "education": "verify with school staff or family, never move funds to safe accounts",
    },
    "enterprise_staff": {
        "label": "enterprise_staff",
        "tone": "clear, efficient, workplace-oriented",
        "focus": "fake leader instructions, fake customer service, investment and wealth scams",
        "education": "use callback verification and do not trust urgent transfer requests in chat tools",
    },
    "self_employed": {
        "label": "self_employed",
        "tone": "practical, transaction-aware",
        "focus": "fake loans, fake police calls, business transfer fraud, cash-flow exploitation",
        "education": "verify counterparties offline and reject upfront-fee financing",
    },
    "retired_group": {
        "label": "retired_group",
        "tone": "warm, simple, step-by-step",
        "focus": "health-product fraud, elder-care investments, fake relatives borrowing money",
        "education": "call family directly before transfers and avoid unknown wealth products",
    },
    "public_officer": {
        "label": "public_officer",
        "tone": "serious, identity-verification first",
        "focus": "phishing emails, fake discipline bodies, fake leader borrowing and data leakage",
        "education": "confirm orders offline and avoid opening unknown links or attachments",
    },
    "finance_practitioner": {
        "label": "finance_practitioner",
        "tone": "professional, strict, process-oriented",
        "focus": "fake boss transfer instructions, fake investment platforms, romance-investment scams",
        "education": "follow maker-checker controls, callback verification, and audit trails",
    },
    "other": {
        "label": "other",
        "tone": "neutral, clear, practical",
        "focus": "prize lures, fake rebates, suspicious links, OTP theft",
        "education": "do not trust, do not click, do not transfer, protect OTPs and payment credentials",
    },
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


def _normalize_from_aliases(raw_value: str, aliases: Dict[str, str], default: str) -> str:
    value = (raw_value or default).strip().lower()
    return aliases.get(value, default)


def normalize_age_group(age_group: str) -> str:
    return _normalize_from_aliases(age_group, AGE_ALIASES, UNKNOWN_VALUE)


def normalize_gender(gender: str) -> str:
    return _normalize_from_aliases(gender, GENDER_ALIASES, UNKNOWN_VALUE)


def normalize_occupation(occupation: str) -> str:
    return _normalize_from_aliases(occupation, OCCUPATION_ALIASES, "other")


def normalize_user_role(user_role: str) -> str:
    return _normalize_from_aliases(user_role, ROLE_ALIASES, GENERAL_ROLE)


def occupation_to_user_role(occupation: str) -> str:
    normalized_occupation = normalize_occupation(occupation)
    mapping = {
        "student": "student",
        "enterprise_staff": "enterprise_staff",
        "self_employed": "self_employed",
        "retired_group": "retired_group",
        "public_officer": "public_officer",
        "finance_practitioner": "finance_practitioner",
        "other": GENERAL_ROLE,
    }
    return mapping.get(normalized_occupation, GENERAL_ROLE)


def get_role_profile(user_role: str) -> Dict[str, str]:
    normalized_role = normalize_user_role(user_role)
    profile = OCCUPATION_PROFILE_MAP.get(normalized_role, OCCUPATION_PROFILE_MAP["other"]).copy()
    profile["role_key"] = normalized_role
    return profile


def get_combined_profile(age_group: str, gender: str, occupation: str, fallback_role: str = GENERAL_ROLE) -> Dict[str, str]:
    normalized_age = normalize_age_group(age_group)
    normalized_gender = normalize_gender(gender)
    normalized_occupation = normalize_occupation(occupation)
    normalized_role = normalize_user_role(fallback_role or occupation_to_user_role(normalized_occupation))

    candidates = [
        (normalized_age, normalized_gender, normalized_occupation),
        (normalized_age, UNKNOWN_VALUE, normalized_occupation),
    ]

    for key in candidates:
        if key in COMPOSITE_PROFILE_MAP:
            profile = COMPOSITE_PROFILE_MAP[key].copy()
            profile.update(
                {
                    "age_group": normalized_age,
                    "gender": normalized_gender,
                    "occupation": normalized_occupation,
                    "user_role": normalized_role,
                }
            )
            return profile

    role_profile = get_role_profile(normalized_role)
    return {
        "age_group": normalized_age,
        "gender": normalized_gender,
        "occupation": normalized_occupation,
        "user_role": normalized_role,
        "risk_level": "low" if normalized_occupation == "other" else "medium",
        "risk_assessment": f"Primary watch-outs: {role_profile['focus']}. Demographic context may change susceptibility and persuasion style.",
        "prompt": f"Key reminder: {role_profile['education']}. Verify identity before transfers and never share OTPs.",
    }


def format_role_profile_text(user_role: str) -> str:
    profile = get_role_profile(user_role)
    return (
        f"role_label: {profile['label']}\n"
        f"tone: {profile['tone']}\n"
        f"focus: {profile['focus']}\n"
        f"education: {profile['education']}"
    )


def format_combined_profile_text(
    age_group: str,
    gender: str,
    occupation: str,
    fallback_role: str = GENERAL_ROLE,
) -> str:
    profile = get_combined_profile(age_group, gender, occupation, fallback_role=fallback_role)
    return (
        f"age_group: {profile['age_group']}\n"
        f"gender: {profile['gender']}\n"
        f"occupation: {profile['occupation']}\n"
        f"risk_level_hint: {profile['risk_level']}\n"
        f"risk_assessment: {profile['risk_assessment']}\n"
        f"personalized_prompt: {profile['prompt']}"
    )


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
    age_group: str = UNKNOWN_VALUE,
    gender: str = UNKNOWN_VALUE,
    occupation: str = "other",
) -> Dict[str, Any]:
    short_term_events = short_term_events or []
    history_profile = history_profile or {}

    low_threshold = DEFAULT_LOW_THRESHOLD
    high_threshold = DEFAULT_HIGH_THRESHOLD
    reasons: List[str] = []

    normalized_role = normalize_user_role(user_role or occupation_to_user_role(occupation))
    normalized_age = normalize_age_group(age_group)
    normalized_gender = normalize_gender(gender)
    normalized_occupation = normalize_occupation(occupation)

    role_profile = get_role_profile(normalized_role)
    combined_profile = get_combined_profile(
        normalized_age,
        normalized_gender,
        normalized_occupation,
        fallback_role=normalized_role,
    )

    for label, deltas in (
        (f"role({normalized_role})", OCCUPATION_THRESHOLD_OFFSETS.get(normalized_occupation, (0, 0))),
        (f"age({normalized_age})", AGE_THRESHOLD_OFFSETS.get(normalized_age, (0, 0))),
        (f"gender({normalized_gender})", GENDER_THRESHOLD_OFFSETS.get(normalized_gender, (0, 0))),
    ):
        low_delta, high_delta = deltas
        if low_delta or high_delta:
            low_threshold += low_delta
            high_threshold += high_delta
            reasons.append(f"{label} threshold shift {low_delta}/{high_delta}")

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
            reasons.append("short_term_risk_persistently_high")
        elif short_avg_score >= 58 or short_high_ratio >= 0.25:
            low_threshold -= 3
            high_threshold -= 3
            reasons.append("short_term_risk_rising")
        elif len(recent_scores) >= 3 and short_avg_score <= 22 and short_high_ratio == 0:
            low_threshold += 2
            high_threshold += 2
            reasons.append("short_term_risk_stable")

    long_total_count = _safe_int(history_profile.get("total_count"), 0)
    long_avg_score = _safe_float(history_profile.get("avg_score"), 0.0)
    long_high_ratio = _safe_float(history_profile.get("high_ratio"), 0.0)
    rising_risk = bool(history_profile.get("rising_risk", False))

    if long_total_count >= 8:
        if long_high_ratio >= 0.35 or long_avg_score >= 64:
            low_threshold -= 4
            high_threshold -= 4
            reasons.append("long_term_high_risk_ratio_elevated")
        elif long_high_ratio <= 0.08 and long_avg_score <= 24:
            low_threshold += 2
            high_threshold += 2
            reasons.append("long_term_risk_low")

    if rising_risk:
        low_threshold -= 2
        high_threshold -= 2
        reasons.append("recent_risk_trend_rising")

    if combined_profile["risk_level"] == "high":
        low_threshold -= 2
        high_threshold -= 2
        reasons.append("composite_profile_high_risk")
    elif combined_profile["risk_level"] == "medium":
        low_threshold -= 1
        high_threshold -= 1
        reasons.append("composite_profile_medium_risk")

    low_threshold, high_threshold = _clamp_thresholds(low_threshold, high_threshold)

    return {
        "normalized_role": normalized_role,
        "normalized_age_group": normalized_age,
        "normalized_gender": normalized_gender,
        "normalized_occupation": normalized_occupation,
        "role_profile": role_profile,
        "combined_profile": combined_profile,
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
