from pathlib import Path


def test_readme_describes_v1_not_minimal_mvp():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "正式版 V1" in text
    assert "最小本地 MVP" not in text
    assert "/api/v1" in text
    assert "BrowserUse 真实平台测试" in text


def test_project_structure_has_current_test_baseline():
    text = Path("docs/project-structure.md").read_text(encoding="utf-8")

    assert "183 passed" in text
    assert "72 passed" not in text
    assert "控制面" in text
    assert "执行面" in text


def test_pyproject_metadata_is_v1():
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "food-ops-agent"' in text
    assert 'version = "1.0.0"' in text
    assert "V1" in text
