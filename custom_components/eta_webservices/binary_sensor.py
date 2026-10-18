"""Binary Sensor platform for the ETA sensor integration in Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant

from .const import ERROR_UPDATE_COORDINATOR
from .coordinator import EtaConfigEntry, ETAErrorUpdateCoordinator
from .entity import EtaErrorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EtaConfigEntry,
    async_add_entities,
):
    """Setup binary sensor."""
    config = config_entry.runtime_data

    error_coordinator = config[ERROR_UPDATE_COORDINATOR]

    sensors = [EtaErrorSensor(config, hass, error_coordinator)]
    async_add_entities(sensors, update_before_add=True)


class EtaErrorSensor(BinarySensorEntity, EtaErrorEntity):
    """Representation of a Binary sensor."""

    def __init__(  # noqa: D107
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        _LOGGER.debug("ETA Integration - init error sensor")

        super().__init__(coordinator, config, "errors")

        self._attr_translation_key = "state_sensor"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

        self.handle_data_updates(self.coordinator.data)

    def handle_data_updates(self, data: list):  # noqa: D102
        self._attr_is_on = len(data) > 0
