"""End-to-end tests for setting up, unloading and servicing a config entry."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.eta_webservices.config_flow import EtaFlowHandler
from custom_components.eta_webservices.const import (
    CHOSEN_FLOAT_SENSORS,
    CHOSEN_PENDING_SENSORS,
    CHOSEN_SWITCHES,
    CHOSEN_TEXT_SENSORS,
    CHOSEN_WRITABLE_SENSORS,
    DOMAIN,
    FLOAT_DICT,
    FORCE_LEGACY_MODE,
    PENDING_DICT,
    SWITCHES_DICT,
    TEXT_DICT,
    WRITABLE_DICT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

NS = 'xmlns="http://www.eta.co.at/rest/v1"'
TEMP_URI = "/120/10601/0/0/12197"


def _entry_data(host: str) -> dict:
    return {
        CONF_HOST: host,
        CONF_PORT: 8080,
        FORCE_LEGACY_MODE: False,
        FLOAT_DICT: {
            "outside_temp": {
                "url": TEMP_URI,
                "value": 10.0,
                "valid_values": None,
                "friendly_name": "Kessel > Outside temperature",
                "unit": "°C",
                "endpoint_type": "DEFAULT",
            }
        },
        SWITCHES_DICT: {},
        TEXT_DICT: {},
        WRITABLE_DICT: {},
        PENDING_DICT: {},
        CHOSEN_FLOAT_SENSORS: ["outside_temp"],
        CHOSEN_SWITCHES: [],
        CHOSEN_TEXT_SENSORS: [],
        CHOSEN_WRITABLE_SENSORS: [],
        CHOSEN_PENDING_SENSORS: [],
    }


def _mock_eta(aioclient_mock: AiohttpClientMocker, host: str) -> None:
    base = f"http://{host}:8080"
    aioclient_mock.get(
        f"{base}/user/var{TEMP_URI}",
        text=(
            f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
            f'<value uri="/user/var{TEMP_URI}" strValue="12,5" unit="°C" '
            'decPlaces="1" scaleFactor="10" advTextOffset="0">125</value></eta>'
        ),
    )
    aioclient_mock.get(
        f"{base}/user/errors",
        text=(
            f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
            '<errors uri="/user/errors"><fub uri="/120/10021" name="Kessel"/>'
            "</errors></eta>"
        ),
    )
    aioclient_mock.post(
        f"{base}/user/var/120/10021/0/0/12080",
        text=(
            f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
            '<success uri="/user/var/120/10021/0/0/12080"/></eta>'
        ),
    )


async def _setup_entry(hass: HomeAssistant, host: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data=_entry_data(host), version=EtaFlowHandler.VERSION
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow loading the integration under test."""


async def test_setup_and_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A config entry loads, exposes its sensor and unloads cleanly."""
    _mock_eta(aioclient_mock, "192.168.0.10")
    entry = await _setup_entry(hass, "192.168.0.10")

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data[CHOSEN_FLOAT_SENSORS] == ["outside_temp"]
    state = hass.states.get("sensor.outside_temp")
    assert state is not None
    assert float(state.state) == 12.5

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Services are registered once for the integration and survive unloading.
    assert hass.services.has_service(DOMAIN, "write_value")


async def test_write_value_single_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """With one ETA system the config entry can be omitted."""
    _mock_eta(aioclient_mock, "192.168.0.10")
    await _setup_entry(hass, "192.168.0.10")

    await hass.services.async_call(
        DOMAIN,
        "write_value",
        {"endpoint_url": "/120/10021/0/0/12080", "value": "1803"},
        blocking=True,
    )

    post_calls = [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
    assert len(post_calls) == 1
    assert (
        str(post_calls[0][1]) == "http://192.168.0.10:8080/user/var/120/10021/0/0/12080"
    )


async def test_write_value_multiple_entries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """With two ETA systems the call must name the target entry."""
    _mock_eta(aioclient_mock, "192.168.0.10")
    _mock_eta(aioclient_mock, "192.168.0.11")
    await _setup_entry(hass, "192.168.0.10")
    second = await _setup_entry(hass, "192.168.0.11")

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "write_value",
            {"endpoint_url": "/120/10021/0/0/12080", "value": "1803"},
            blocking=True,
        )

    await hass.services.async_call(
        DOMAIN,
        "write_value",
        {
            "config_entry_id": second.entry_id,
            "endpoint_url": "/120/10021/0/0/12080",
            "value": "1803",
        },
        blocking=True,
    )
    post_calls = [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
    assert [str(call[1]) for call in post_calls] == [
        "http://192.168.0.11:8080/user/var/120/10021/0/0/12080"
    ]
