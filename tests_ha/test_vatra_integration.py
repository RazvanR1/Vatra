from homeassistant import config_entries
from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.setup import async_setup_component

URL = "http://vatra-host:8099/api/conversation"
DATA = {"host": "vatra-host", "port": 8099, "token": "secret"}


async def test_user_flow_and_conversation(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(URL, json={"speech": "Am stins lumina din hol.", "conversation_id": "c1"})
    assert await async_setup_component(hass, "conversation", {})
    result = await hass.config_entries.flow.async_init("vatra", context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["data"] == DATA
    await hass.async_block_till_done()

    state = hass.states.get("conversation.vatra_jarvis")
    assert state is not None
    res = await conversation.async_converse(hass, "stinge lumina din hol", None, Context(),
                                            language="ro", agent_id="conversation.vatra_jarvis")
    assert res.response.speech["plain"]["speech"] == "Am stins lumina din hol."
    call = aioclient_mock.mock_calls[-1]
    assert call[2]["text"] == "stinge lumina din hol"
    assert call[3]["X-Vatra-Token"] == "secret"


async def test_bad_token_shows_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(URL, status=403)
    result = await hass.config_entries.flow.async_init("vatra", context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "invalid_auth"}


async def test_hassio_discovery(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(URL, json={"speech": "", "conversation_id": "x"})
    info = HassioServiceInfo(config=DATA, name="Vatra", slug="0bf38c22_ha_home_brain", uuid="1234")
    result = await hass.config_entries.flow.async_init("vatra", context={"source": config_entries.SOURCE_HASSIO},
                                                       data=info)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "hassio_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["data"] == DATA


async def test_vatra_down_gives_spoken_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(URL, json={"speech": "", "conversation_id": "x"})
    assert await async_setup_component(hass, "conversation", {})
    r = await hass.config_entries.flow.async_init("vatra", context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(r["flow_id"], DATA)
    await hass.async_block_till_done()
    aioclient_mock.clear_requests()
    aioclient_mock.post(URL, exc=TimeoutError())
    res = await conversation.async_converse(hass, "salut", None, Context(), language="ro",
                                            agent_id="conversation.vatra_jarvis")
    assert res.response.speech["plain"]["speech"] == "Vatra nu răspunde acum."
