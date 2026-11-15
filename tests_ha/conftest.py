"""Teste pentru integrarea custom_components/vatra (rulează cu pytest-homeassistant-custom-component)."""
import pathlib
import sys

import pytest

# Home Assistant pune folderul de config de test primul în sys.path; importăm din timp pachetul nostru.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import custom_components  # noqa: E402,F401

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
async def base_setup(hass, enable_custom_integrations):
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, "homeassistant", {})
    yield
