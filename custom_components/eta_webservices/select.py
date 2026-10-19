"""Select platform for the ETA sensor integration in Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import ETAEndpoint
from .const import (
    CHOSEN_WRITABLE_SENSORS,
    CUSTOM_UNIT_SELECT,
    WRITABLE_DICT,
    WRITABLE_UPDATE_COORDINATOR,
)
from .coordinator import EtaConfigEntry, ETAWritableUpdateCoordinator
from .entity import EtaCoordinatedSensorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EtaConfigEntry,
    async_add_entities,
):
    """Setup select entities from a config entry created in the integrations UI."""
    config = config_entry.runtime_data

    coordinator = config[WRITABLE_UPDATE_COORDINATOR]

    selects = [
        EtaSelect(config, hass, entity, config[WRITABLE_DICT][entity], coordinator)
        for entity in config[CHOSEN_WRITABLE_SENSORS]
        if config[WRITABLE_DICT][entity]["unit"] == CUSTOM_UNIT_SELECT
    ]
    async_add_entities(selects)


class EtaSelect(SelectEntity, EtaCoordinatedSensorEntity[str]):
    """A writable variable with named values, e.g. "Frei" and "Gesperrt"."""

    def __init__(  # noqa: D107
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        coordinator: ETAWritableUpdateCoordinator,
    ) -> None:
        # Maps the displayed value to the raw value written to the terminal
        self.raw_values: dict[str, int] = endpoint_info["valid_values"]  # pyright: ignore[reportAttributeAccessIssue]
        self._attr_options = list(self.raw_values)
        self._attr_entity_category = EntityCategory.CONFIG

        super().__init__(coordinator, config, hass, unique_id, endpoint_info)

    def handle_data_updates(self, data: str | None) -> None:  # noqa: D102
        if data is not None and data not in self.raw_values:
            _LOGGER.info(
                "Select %s received unknown value '%s'; setting state to unknown",
                self.entity_id,
                data,
            )
            data = None
        self._attr_current_option = data

    async def async_select_option(self, option: str) -> None:
        """Write the raw value of the option to the terminal."""
        eta_client = self._create_eta_client()
        if not await eta_client.write_endpoint(self.uri, self.raw_values[option]):
            raise HomeAssistantError(
                f"Could not write value for entity {self.entity_id}, see log for details"
            )
        await self.coordinator.async_refresh()
