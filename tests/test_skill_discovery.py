from pathlib import Path

import pytest

from ai_tools.agent_runtime.errors import SkillValidationError
from ai_tools.agent_runtime.skills import discover_skills


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_discover_repo_skills():
    registry = discover_skills(PROJECT_ROOT / "skills")
    expected = {
        "proofread-general",
        "proofread-slack",
        "proofread-email",
        "explain",
        "commands",
        "ask",
        "refresh-llms",
    }
    assert expected.issubset(set(registry.keys()))


def test_invalid_skill_schema_raises(tmp_path: Path):
    bad = tmp_path / "skills" / "bad-skill"
    bad.mkdir(parents=True)
    (bad / "SKILL.md").write_text("""---\nname: test\n---\nbody""", encoding="utf-8")

    with pytest.raises(SkillValidationError) as exc:
        discover_skills(tmp_path / "skills")

    assert exc.value.code == "SKILL_INVALID_SCHEMA"
