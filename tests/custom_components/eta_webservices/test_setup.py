"""End-to-end tests for setting up, unloading and servicing a config entry."""

import re

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
    SENSOR_UPDATE_COORDINATOR,
    SWITCHES_DICT,
    TEXT_DICT,
    WRITABLE_DICT,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

NS = 'xmlns="http://www.eta.co.at/rest/v1"'
TEMP_URI = "/120/10601/0/0/12197"
TEMP_KEY = "120_10601_0_0_12197"
SLOT_URI = "/120/10111/12130/0/1082"
SLOT_KEY = "120_10111_12130_0_1082_writable"
SELECT_URI = "/40/10211/0/0/12262"
SELECT_KEY = "40_10211_0_0_12262_writable"


def _entry_data(host: str) -> dict:
    return {
        CONF_HOST: host,
        CONF_PORT: 8080,
        FORCE_LEGACY_MODE: False,
        FLOAT_DICT: {
            TEMP_KEY: {
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
        WRITABLE_DICT: {
            SLOT_KEY: {
                "url": SLOT_URI,
                "value": "15:30 - 18:00 55",
                "valid_values": {
                    "scaled_min_value": 0.0,
                    "scaled_max_value": 90.0,
                    "scale_factor": 10,
                    "dec_places": 0,
                },
                "friendly_name": "Warmwasserspeicher > Ladezeiten > Montag > Zeitfenster 1",
                "unit": "timeslot_plus_temperature",
                "endpoint_type": "TIMESLOT",
            },
            SELECT_KEY: {
                "url": SELECT_URI,
                "value": "Frei",
                "valid_values": {"Frei": 1804, "Gesperrt": 1805},
                "friendly_name": "LagerUm. > Sonstiges > Position 1",
                "unit": "select",
                "endpoint_type": "TEXT",
            },
        },
        PENDING_DICT: {},
        CHOSEN_FLOAT_SENSORS: [TEMP_KEY],
        CHOSEN_SWITCHES: [],
        CHOSEN_TEXT_SENSORS: [],
        CHOSEN_WRITABLE_SENSORS: [SLOT_KEY, SELECT_KEY],
        CHOSEN_PENDING_SENSORS: [],
    }


def _mock_eta(
    aioclient_mock: AiohttpClientMocker, host: str, vars_supported: bool = True
) -> None:
    base = f"http://{host}:8080"
    vars_url = re.compile(rf"^{re.escape(base)}/user/vars/")
    if vars_supported:
        aioclient_mock.delete(vars_url, status=200)
        aioclient_mock.put(vars_url, status=201)
        aioclient_mock.get(
            vars_url,
            text=(
                f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
                '<vars uri="/user/vars/set">'
                f'<variable uri="{TEMP_URI.lstrip("/")}" strValue="13,5" unit="°C" '
                'decPlaces="1" scaleFactor="10" advTextOffset="0">135</variable>'
                f'<variable uri="{SLOT_URI.lstrip("/")}" strValue="15:30 - 18:00 55" '
                'unit="°C" decPlaces="0" scaleFactor="10" advTextOffset="0">0'
                f'</variable><variable uri="{SELECT_URI.lstrip("/")}" strValue="Frei" '
                'unit="" decPlaces="0" scaleFactor="1" advTextOffset="1804">1804'
                "</variable></vars></eta>"
            ),
        )
    else:
        aioclient_mock.delete(vars_url, status=404)
        aioclient_mock.put(vars_url, status=404)
    aioclient_mock.get(
        f"{base}/user/var{TEMP_URI}",
        text=(
            f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
            f'<value uri="/user/var{TEMP_URI}" strValue="12,5" unit="°C" '
            'decPlaces="1" scaleFactor="10" advTextOffset="0">125</value></eta>'
        ),
    )
    aioclient_mock.get(
        f"{base}/user/var{SLOT_URI}",
        text=(
            f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
            f'<value uri="/user/var{SLOT_URI}" strValue="15:30 - 18:00 55" '
            'unit="°C" decPlaces="0" scaleFactor="10" advTextOffset="0">0</value>'
            "</eta>"
        ),
    )
    aioclient_mock.post(
        f"{base}/user/var{SLOT_URI}",
        text=(
            f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
            f'<success uri="/user/var{SLOT_URI}"/></eta>'
        ),
    )
    aioclient_mock.get(
        f"{base}/user/var{SELECT_URI}",
        text=(
            f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
            f'<value uri="/user/var{SELECT_URI}" strValue="Frei" unit="" '
            'decPlaces="0" scaleFactor="1" advTextOffset="1804">1804</value></eta>'
        ),
    )
    aioclient_mock.post(
        f"{base}/user/var{SELECT_URI}",
        text=(
            f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
            f'<success uri="/user/var{SELECT_URI}"/></eta>'
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
        domain=DOMAIN,
        data=_entry_data(host),
        unique_id=f"{host}:8080",
        version=EtaFlowHandler.VERSION,
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
    assert entry.runtime_data[CHOSEN_FLOAT_SENSORS] == [TEMP_KEY]

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{TEMP_KEY}"
    )
    # The entity ID is generated from the device and entity names
    assert entity_id == "sensor.kessel_outside_temperature"
    # The value comes from the variable set, not the single variable
    state = hass.states.get(entity_id)
    assert float(state.state) == 13.5

    device_registry = dr.async_get(hass)
    terminal = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    kessel = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_Kessel")}
    )
    assert terminal.name == "ETA"
    assert kessel.name == "Kessel"
    assert kessel.via_device_id == terminal.id

    aioclient_mock.mock_calls.clear()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # The variable sets of both coordinators are deleted on unload
    deleted = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert len(deleted) == 2
    assert all("/user/vars/ha" in url for url in deleted)
    # Services are registered once for the integration and survive unloading.
    assert hass.services.has_service(DOMAIN, "write_value")


async def test_falls_back_to_single_variables(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Terminals refusing variable sets are read one variable at a time."""
    _mock_eta(aioclient_mock, "192.168.0.10", vars_supported=False)
    entry = await _setup_entry(hass, "192.168.0.10")

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{TEMP_KEY}"
    )
    assert float(hass.states.get(entity_id).state) == 12.5

    # The set is not tried again on the next update
    aioclient_mock.mock_calls.clear()
    await entry.runtime_data[SENSOR_UPDATE_COORDINATOR].async_refresh()
    urls = {str(call[1]) for call in aioclient_mock.mock_calls}
    assert urls == {
        f"http://192.168.0.10:8080/user/var{TEMP_URI}",
        f"http://192.168.0.10:8080/user/var{SLOT_URI}",
    }


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


async def test_write_timeslot(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The write_timeslot service posts value, begin and end to the slot."""
    _mock_eta(aioclient_mock, "192.168.0.10")
    entry = await _setup_entry(hass, "192.168.0.10")
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{SLOT_KEY}"
    )
    assert hass.states.get(entity_id).state == "15:30 - 18:00: 55 °C"

    await hass.services.async_call(
        DOMAIN,
        "write_timeslot",
        {"entity_id": entity_id, "begin": "06:00", "end": "08:30", "temperature": 50},
        blocking=True,
    )

    post_calls = [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
    assert len(post_calls) == 1
    assert str(post_calls[0][1]).endswith(f"/user/var{SLOT_URI}")
    assert post_calls[0][2] == {"value": 500, "begin": 24, "end": 34}


async def test_select_option(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Selecting an option writes its raw value."""
    _mock_eta(aioclient_mock, "192.168.0.10")
    entry = await _setup_entry(hass, "192.168.0.10")
    entity_id = er.async_get(hass).async_get_entity_id(
        "select", DOMAIN, f"{entry.entry_id}_{SELECT_KEY}"
    )
    state = hass.states.get(entity_id)
    assert state.state == "Frei"
    assert state.attributes["options"] == ["Frei", "Gesperrt"]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Gesperrt"},
        blocking=True,
    )

    post_calls = [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
    assert len(post_calls) == 1
    assert str(post_calls[0][1]).endswith(f"/user/var{SELECT_URI}")
    assert post_calls[0][2] == {"value": 1805}


async def test_same_system_cannot_be_added_twice(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The config flow aborts for a host and port that is already set up."""
    _mock_eta(aioclient_mock, "192.168.0.10")
    await _setup_entry(hass, "192.168.0.10")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.10", CONF_PORT: 8080},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_setup_retries_when_terminal_returns_no_values(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Setup is retried instead of creating entities without any values."""
    base = "http://192.168.0.10:8080"
    aioclient_mock.get(f"{base}/user/errors", text=f"<eta {NS}><errors/></eta>")
    vars_url = re.compile(rf"^{re.escape(base)}/user/vars/")
    for method in ("delete", "put", "get"):
        aioclient_mock.request(method, vars_url, status=500)
    aioclient_mock.get(f"{base}/user/var{TEMP_URI}", status=500)
    aioclient_mock.get(f"{base}/user/var{SLOT_URI}", status=500)
    aioclient_mock.get(f"{base}/user/var{SELECT_URI}", status=500)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_entry_data("192.168.0.10"),
        unique_id="192.168.0.10:8080",
        version=EtaFlowHandler.VERSION,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
