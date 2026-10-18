"""Button platform for the ETA sensor integration in Home Assistant."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ENTRY_ID, ERROR_UPDATE_COORDINATOR
from .coordinator import EtaConfigEntry, ETAErrorUpdateCoordinator
from .utils import create_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EtaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup button."""
    config = config_entry.runtime_data
    error_coordinator = config[ERROR_UPDATE_COORDINATOR]

    buttons = [
        EtaResendErrorEventsButton(config, hass, error_coordinator),
    ]

    async_add_entities(buttons)


class EtaResendErrorEventsButton(ButtonEntity):
    """Representation of a Button."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(  # noqa: D107
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        self.coordinator = coordinator

        self._attr_translation_key = "send_error_events_btn"
        self._attr_unique_id = f"{config[ENTRY_ID]}_send_events_btn"
        self._attr_device_info = create_device_info(config[ENTRY_ID], None)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Force the error update coordinator to resend all error events."""
        # Delete the old error list to force the coordinator to resend all events
        self.coordinator.data = []
        await self.coordinator.async_refresh()
