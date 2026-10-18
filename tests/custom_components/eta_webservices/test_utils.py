"""Unit tests for utility functions."""

# pyright: reportTypedDictNotRequiredAccess=false

from custom_components.eta_webservices.const import DOMAIN
from custom_components.eta_webservices.utils import (
    create_device_info,
    endpoint_key,
    endpoint_key_from_unique_id,
    entity_unique_id,
)


def test_create_device_info_with_device_name():
    """A functional block becomes its own device below the terminal."""
    info = create_device_info("entry1", "Kessel")
    assert info["name"] == "Kessel"
    assert (DOMAIN, "entry1_Kessel") in info["identifiers"]
    assert info["via_device"] == (DOMAIN, "entry1")
    assert info["manufacturer"] == "ETA"


def test_create_device_info_without_device_name():
    """Omitting device_name yields the terminal device itself."""
    info = create_device_info("entry1", None)
    assert info["name"] == "ETA"
    assert (DOMAIN, "entry1") in info["identifiers"]
    assert "via_device" not in info
    assert info["configuration_url"] == "https://www.meineta.at"


def test_endpoint_key_is_derived_from_uri():
    """Keys depend only on the CAN address, not on host or menu names."""
    assert endpoint_key("/40/10021/0/0/12080") == "40_10021_0_0_12080"


def test_unique_id_round_trip():
    """The endpoint key can be recovered from an entity unique_id."""
    unique_id = entity_unique_id("entry1", "40_10021_0_0_12080_writable")
    assert unique_id == "entry1_40_10021_0_0_12080_writable"
    assert endpoint_key_from_unique_id("entry1", unique_id) == (
        "40_10021_0_0_12080_writable"
    )
    assert endpoint_key_from_unique_id("entry2", unique_id) is None
