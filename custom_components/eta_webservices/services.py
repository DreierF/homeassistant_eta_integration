"""Low-level service support for ETA Sensors."""

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EtaAPI
from .const import (
    DEFAULT_MAX_PARALLEL_REQUESTS,
    DOMAIN,
    MAX_PARALLEL_REQUESTS,
    REQUEST_SEMAPHORE,
)
from .coordinator import EtaConfigEntry

ATTR_CONFIG_ENTRY_ID = "config_entry_id"

WRITE_ENDPOINT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("endpoint_url"): cv.string,
        vol.Required("value"): cv.string,
        vol.Optional("begin"): vol.All(vol.Coerce(int), vol.Range(min=0, max=96)),
        vol.Optional("end"): vol.All(vol.Coerce(int), vol.Range(min=0, max=96)),
    },
)


def _get_target_entry(hass: HomeAssistant, call: ServiceCall) -> EtaConfigEntry:
    """Return the loaded config entry a service call is aimed at.

    The entry may be omitted when exactly one ETA system is set up, which keeps
    automations written before multi-entry support working.
    """
    loaded_entries: list[EtaConfigEntry] = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id is None:
        if len(loaded_entries) != 1:
            raise ServiceValidationError(
                f"Specify {ATTR_CONFIG_ENTRY_ID} when more than one ETA system is set up"
            )
        return loaded_entries[0]

    for entry in loaded_entries:
        if entry.entry_id == entry_id:
            return entry
    raise ServiceValidationError(f"No loaded ETA config entry with id {entry_id}")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Setup low-level services, as defined in the services.yaml file."""

    async def handle_write(call: ServiceCall):
        """Handle the service call."""
        config = _get_target_entry(hass, call).runtime_data
        url = call.data.get("endpoint_url", "")
        value = call.data.get("value")
        begin = call.data.get("begin", None)
        end = call.data.get("end", None)
        eta_client = EtaAPI(
            async_get_clientsession(hass),
            config.get(CONF_HOST),
            config.get(CONF_PORT),
            max_concurrent_requests=config.get(
                MAX_PARALLEL_REQUESTS, DEFAULT_MAX_PARALLEL_REQUESTS
            ),
            request_semaphore=config.get(REQUEST_SEMAPHORE),
        )
        success = await eta_client.write_endpoint(url, value, begin, end)
        if not success:
            raise HomeAssistantError("Could not write value, see log for details")

    hass.services.async_register(
        DOMAIN, "write_value", handle_write, schema=WRITE_ENDPOINT_SCHEMA
    )
