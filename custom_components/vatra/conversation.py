"""Agentul de conversație „Vatra (Jarvis)”: textul din Assist merge la Jarvis din add-on."""
from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import VatraAuthError, VatraError, ask
from .const import CONF_TOKEN, DOMAIN

ERRORS = {
    "en": ("Vatra is not responding right now.", "Vatra refused the request – reconfigure the Vatra integration."),
    "ro": ("Vatra nu răspunde acum.", "Vatra a refuzat cererea – reconfigurează integrarea Vatra."),
    "hu": ("A Vatra most nem válaszol.", "A Vatra elutasította a kérést – állítsd be újra a Vatra integrációt."),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([VatraConversationEntity(entry)])


class VatraConversationEntity(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = "Jarvis"
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_jarvis"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="Vatra",
                                            manufacturer="RazvanR1", model="Vatra add-on")

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def _async_handle_message(self, user_input: conversation.ConversationInput,
                                    chat_log: conversation.ChatLog) -> conversation.ConversationResult:
        lang = (user_input.language or "en").split("-")[0]
        data = self.entry.data
        try:
            result = await ask(async_get_clientsession(self.hass), data[CONF_HOST], int(data[CONF_PORT]),
                               data[CONF_TOKEN], user_input.text, chat_log.conversation_id, user_input.language)
            speech = result.get("speech") or ""
        except VatraAuthError:
            speech = ERRORS.get(lang, ERRORS["en"])[1]
        except VatraError:
            speech = ERRORS.get(lang, ERRORS["en"])[0]
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=user_input.agent_id, content=speech))
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(speech)
        return conversation.ConversationResult(response=response, conversation_id=chat_log.conversation_id)
