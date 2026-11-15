"""Configurare: automat (Vatra se anunță singur) sau manual (adresă + cod din panoul Vatra)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import VatraAuthError, VatraError, ask
from .const import CONF_TOKEN, DEFAULT_PORT, DOMAIN


class VatraConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def _check(self, data: dict[str, Any]) -> str | None:
        try:
            await ask(async_get_clientsession(self.hass), data[CONF_HOST], int(data[CONF_PORT]),
                      data[CONF_TOKEN], "", timeout=15)
        except VatraAuthError:
            return "invalid_auth"
        except VatraError:
            return "cannot_connect"
        return None

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        cfg = discovery_info.config
        self._data = {CONF_HOST: cfg["host"], CONF_PORT: int(cfg.get("port", DEFAULT_PORT)),
                      CONF_TOKEN: cfg["token"]}
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(updates=self._data)
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (err := await self._check(self._data)):
                return self.async_create_entry(title="Vatra", data=self._data)
            errors["base"] = err
        return self.async_show_form(step_id="hassio_confirm", errors=errors)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (err := await self._check(user_input)):
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title="Vatra", data=user_input)
            errors["base"] = err
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_TOKEN): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
