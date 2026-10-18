"""The ETA Sensors integration."""

import asyncio
import logging

from homeassistant import config_entries, core
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    DEFAULT_MAX_PARALLEL_REQUESTS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_ID,
    ERROR_UPDATE_COORDINATOR,
    MAX_PARALLEL_REQUESTS,
    PENDING_UPDATE_COORDINATOR,
    REQUEST_SEMAPHORE,
    SENSOR_UPDATE_COORDINATOR,
    UPDATE_INTERVAL,
    WRITABLE_UPDATE_COORDINATOR,
)
from .coordinator import (
    EtaConfigEntry,
    ETAErrorUpdateCoordinator,
    ETAPendingNodeCoordinator,
    ETASensorUpdateCoordinator,
    ETAWritableUpdateCoordinator,
)
from .services import async_setup_services
from .utils import create_device_info

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: core.HomeAssistant, config: ConfigType) -> bool:
    """Register the integration-wide services."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: core.HomeAssistant, entry: EtaConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    config = dict(entry.data)
    # Registers update listener to update config entry when options are updated.
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    # Merge the options with the config
    # The options are set if a user configures the integration after the initial set-up
    if entry.options:
        config.update(entry.options)

    config[MAX_PARALLEL_REQUESTS] = int(
        config.get(MAX_PARALLEL_REQUESTS, DEFAULT_MAX_PARALLEL_REQUESTS)
    )
    config[UPDATE_INTERVAL] = int(config.get(UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
    # Share one limiter across all API users of this config entry
    # so startup and periodic updates cannot overload slower ETA units.
    config[REQUEST_SEMAPHORE] = asyncio.Semaphore(config[MAX_PARALLEL_REQUESTS])
    config[ENTRY_ID] = entry.entry_id

    # Register the terminal before the platforms, as the devices of the
    # functional blocks reference it via via_device.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **create_device_info(entry.entry_id, None),
    )

    error_coordinator = ETAErrorUpdateCoordinator(hass, config, entry)
    sensor_coordinator = ETASensorUpdateCoordinator(hass, config, entry)
    writable_coordinator = ETAWritableUpdateCoordinator(hass, config, entry)
    pending_coordinator = ETAPendingNodeCoordinator(hass, config, entry)
    config[ERROR_UPDATE_COORDINATOR] = error_coordinator
    config[SENSOR_UPDATE_COORDINATOR] = sensor_coordinator
    config[WRITABLE_UPDATE_COORDINATOR] = writable_coordinator
    config[PENDING_UPDATE_COORDINATOR] = pending_coordinator

    # Prime coordinators once before entities are added to avoid initial update bursts.
    await error_coordinator.async_config_entry_first_refresh()
    await sensor_coordinator.async_config_entry_first_refresh()
    await writable_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = config

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Schedule the pending-node check after platform setup so that the
    # options_update_listener (registered above) is already in place before
    # any promotion fires and updates the options.
    hass.async_create_task(pending_coordinator.async_refresh())

    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: core.HomeAssistant, entry: EtaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
