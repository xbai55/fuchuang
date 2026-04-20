from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _requirement_lines() -> list[str]:
    return [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_postgres_checkpointer_dependencies_are_declared():
    requirements = _requirement_lines()

    assert any(line.startswith("langgraph-checkpoint-postgres") for line in requirements)
    assert any(line.startswith("psycopg[") or line.startswith("psycopg==") for line in requirements)


def test_postgres_checkpointer_fallback_log_has_install_hint():
    source = (ROOT / "src" / "storage" / "memory" / "memory_saver.py").read_text(encoding="utf-8")

    assert "psycopg[binary,pool]" in source
    assert "langgraph-checkpoint-postgres" in source


def test_postgres_checkpointer_env_var_is_documented():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "PGDATABASE_URL=" in env_example
