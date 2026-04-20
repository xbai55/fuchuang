from src.core.utils.risk_personalization import build_role_prompt_guidance


def test_build_role_prompt_guidance_student_role():
    guidance = build_role_prompt_guidance("student", language="zh-CN")

    assert "Role=student" in guidance
    assert "campus loans" in guidance
    assert "OTP" in guidance or "otp" in guidance.lower()


def test_build_role_prompt_guidance_normalizes_finance_alias():
    guidance = build_role_prompt_guidance("finance", language="en-US")

    assert "Role=finance_practitioner" in guidance
    assert "maker-checker" in guidance