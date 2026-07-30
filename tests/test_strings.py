"""Sanity tests for strings.json / translations."""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
STRINGS_PATH = REPO_ROOT / "custom_components" / "adblock_manager" / "strings.json"
TRANSLATION_PATH = (
    REPO_ROOT
    / "custom_components"
    / "adblock_manager"
    / "translations"
    / "en.json"
)


def test_strings_covers_all_flow_steps():
    strings = json.loads(STRINGS_PATH.read_text())
    steps = strings["config"]["step"]
    for step_id in ("user", "technitium", "pihole", "reauth_confirm"):
        assert step_id in steps


def test_translation_file_matches_strings():
    strings = json.loads(STRINGS_PATH.read_text())
    translation = json.loads(TRANSLATION_PATH.read_text())
    assert translation == strings
