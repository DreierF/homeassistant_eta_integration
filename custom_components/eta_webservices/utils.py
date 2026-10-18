"""Various utility functions."""

from homeassistant.helpers.device_registry import DeviceInfo

from ._api.api_client import endpoint_key  # noqa: F401
from .const import CUSTOM_UNIT_UNITLESS, DOMAIN


def entity_unique_id(entry_id: str, key: str) -> str:
    """Return the unique_id of the entity for an endpoint key of a config entry."""
    return f"{entry_id}_{key}"


def endpoint_key_from_unique_id(entry_id: str, unique_id: str) -> str | None:
    """Return the endpoint key of an entity unique_id, None if it is no endpoint entity."""
    prefix = f"{entry_id}_"
    return unique_id.removeprefix(prefix) if unique_id.startswith(prefix) else None


def create_device_info(entry_id: str, device_name: str | None) -> DeviceInfo:
    """Create the DeviceInfo for the ETA terminal or one of its functional blocks.

    Entities without a functional block, like the error sensors, belong to the
    terminal itself; all others belong to a device per functional block (e.g.
    "Kessel") that is linked to the terminal.
    """
    if device_name is None:
        return DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="ETA",
            manufacturer="ETA",
            configuration_url="https://www.meineta.at",
        )
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{device_name}")},
        name=device_name,
        manufacturer="ETA",
        via_device=(DOMAIN, entry_id),
    )


def get_native_unit(unit):
    """Convert ETA API units to Home Assistant native units."""
    if unit == "%rH":
        return "%"
    if unit == "":
        return None
    if unit == CUSTOM_UNIT_UNITLESS:
        return None
    return unit
