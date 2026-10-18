"""Tests pinning behaviour to the ETAtouch RESTful webservices spec v1.2."""

from datetime import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientSession
import pytest
import xmltodict

from custom_components.eta_webservices._api.api_client import resource_path
from custom_components.eta_webservices._api.sensor_discovery_v12 import (
    SensorDiscoveryV12,
)
from custom_components.eta_webservices.api import EtaAPI
from custom_components.eta_webservices.const import (
    CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE,
)
from custom_components.eta_webservices.number import EtaWritableNumberSensor
from custom_components.eta_webservices.sensor import EtaTimeslotSensor

NS = 'xmlns="http://www.eta.co.at/rest/v1"'


def _api_returning(xml: str) -> EtaAPI:
    api = EtaAPI(AsyncMock(spec=ClientSession), "192.168.0.1", 8080)

    async def mock_get_request(suffix):
        response = AsyncMock()
        response.text = AsyncMock(return_value=xml)
        return response

    api._http.get_request = mock_get_request
    return api


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("/112/10021/0/0/12112", "/user/var/112/10021/0/0/12112"),
        ("112/10021/0/0/12112", "/user/var/112/10021/0/0/12112"),
    ],
)
def test_resource_path_has_single_slash(uri, expected):
    """Menu URIs with or without a leading slash map to the spec's path."""
    assert resource_path("/user/var", uri) == expected


@pytest.mark.parametrize(
    "errors_element",
    [
        '<errors uri="/user/errors"/>',
        "<errors/>",
    ],
)
async def test_get_errors_without_functional_blocks(errors_element):
    """An errors element without any <fub> children means no active errors."""
    api = _api_returning(
        f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
        f"{errors_element}</eta>"
    )
    assert await api.get_errors() == []


async def test_get_errors_without_error_text():
    """An <error> without a description still yields an error."""
    api = _api_returning(
        f'<?xml version="1.0" encoding="utf-8"?><eta version="1.0" {NS}>'
        '<errors uri="/user/errors"><fub uri="/112/10021" name="Kessel">'
        '<error msg="Flue gas sensor Interrupted" priority="Error" '
        'time="2011-06-29 12:47:50"/></fub></errors></eta>'
    )
    errors = await api.get_errors()
    assert len(errors) == 1
    assert errors[0]["msg"] == "Flue gas sensor Interrupted"
    assert errors[0]["text"] == ""


def test_varinfo_with_single_valid_value():
    """validValues with a single <value> must not be iterated as dict keys."""
    xml = (
        f'<eta version="1.0" {NS}><varInfo uri="/user/varinfo/40/10021/0/0/12080">'
        '<variable uri="40/10021/0/0/12080" name="Mode" fullName="Misc. &gt; Mode" '
        'unit="" decPlaces="0" scaleFactor="1" advTextOffset="1802" isWritable="0">'
        "<type>TEXT</type>"
        '<validValues><value strValue="Auto">1802</value></validValues>'
        "</variable></varInfo></eta>"
    )
    data = xmltodict.parse(xml)["eta"]["varInfo"]["variable"]
    discovery = SensorDiscoveryV12(MagicMock())

    endpoint = discovery._parse_varinfo(data, "Kessel", "/40/10021/0/0/12080")

    assert endpoint["valid_values"] == {"Auto": 1802}


@pytest.mark.parametrize(
    ("endpoint_type", "value", "expected"),
    [
        # Scaled integer variables are posted as integers (spec 4.2: raw value)
        ("DEFAULT", 20.56, 206),
        ("DEFAULT", 20.0, 200),
        # IEEE-754 variables keep their fractional raw value
        ("IEEE-754", 20.56, 206.0),
    ],
)
async def test_number_writes_raw_values(hass, endpoint_type, value, expected):
    """Writable numbers post the raw value without a spurious decimal part."""
    coordinator = MagicMock()
    coordinator.data = {"/120/10101/0/0/12345": 20.0}
    coordinator.async_refresh = AsyncMock()
    sensor = EtaWritableNumberSensor(
        {"host": "192.168.0.25", "port": 8080},
        hass,
        "boiler_temp",
        {
            "url": "/120/10101/0/0/12345",
            "value": 20.0,
            "valid_values": {
                "scaled_min_value": 5.0,
                "scaled_max_value": 30.0,
                "scale_factor": 10,
                "dec_places": 1,
            },
            "friendly_name": "Kessel > Boiler temperature",
            "unit": "°C",
            "endpoint_type": endpoint_type,
        },
        coordinator,
    )
    client = MagicMock()
    client.write_endpoint = AsyncMock(return_value=True)
    sensor._create_eta_client = MagicMock(return_value=client)

    await sensor.async_set_native_value(value)

    written = client.write_endpoint.await_args.args[1]
    assert written == expected
    assert type(written) is type(expected)


async def test_timeslot_write_with_zero_degrees(hass):
    """0 °C is a temperature and must be sent as value=0, not omitted."""
    coordinator = MagicMock()
    coordinator.data = {"/120/10111/12130/0/1082": "00:00 - 12:00 40"}
    coordinator.async_refresh = AsyncMock()
    sensor = EtaTimeslotSensor(
        {"host": "192.168.0.25", "port": 8080},
        hass,
        "tank_slot",
        {
            "url": "/120/10111/12130/0/1082",
            "value": "00:00 - 12:00 40",
            "valid_values": {
                "scaled_min_value": -10.0,
                "scaled_max_value": 90.0,
                "scale_factor": 10,
                "dec_places": 1,
            },
            "friendly_name": "Boiler > Charging times",
            "unit": CUSTOM_UNIT_TIMESLOT_PLUS_TEMPERATURE,
            "endpoint_type": "TIMESLOT",
        },
        coordinator,
        should_activate_service=True,
    )
    client = MagicMock()
    client.write_endpoint = AsyncMock(return_value=True)
    sensor._create_eta_client = MagicMock(return_value=client)

    await sensor.async_update_timeslot_service(time(0, 0), time(12, 0), 0.0)

    client.write_endpoint.assert_awaited_once_with("/120/10111/12130/0/1082", 0, 0, 48)
