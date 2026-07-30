"""Sanity tests for the integration manifest and HACS metadata."""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = REPO_ROOT / "custom_components" / "adblock_manager" / "manifest.json"
HACS_PATH = REPO_ROOT / "hacs.json"


def test_manifest_has_required_keys():
    manifest = json.loads(MANIFEST_PATH.read_text())
    for key in (
        "domain",
        "name",
        "codeowners",
        "config_flow",
        "documentation",
        "requirements",
        "version",
    ):
        assert key in manifest
    assert manifest["domain"] == "adblock_manager"
    assert manifest["config_flow"] is True
    assert manifest["requirements"] == []


def test_hacs_json_is_valid():
    hacs = json.loads(HACS_PATH.read_text())
    assert hacs["name"]
    assert "content_in_root" not in hacs
