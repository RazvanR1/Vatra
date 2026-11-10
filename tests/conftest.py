import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_home_brain"))

from app import i18n  # noqa: E402


@pytest.fixture(autouse=True)
def romanian_by_default():
    """Testele vechi verifică textele în română; testele de engleză schimbă limba explicit."""
    i18n.set_language("ro")
    yield
    i18n.set_language("ro")
