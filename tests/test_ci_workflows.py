"""Sanity tests for CI workflow YAML files."""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def test_test_workflow_is_valid_yaml():
    workflow = yaml.safe_load((WORKFLOWS_DIR / "test.yml").read_text())
    assert "jobs" in workflow
    assert "pytest" in workflow["jobs"]


def test_hacs_workflow_is_valid_yaml():
    workflow = yaml.safe_load((WORKFLOWS_DIR / "hacs.yml").read_text())
    assert "jobs" in workflow
    assert "hacs" in workflow["jobs"]
